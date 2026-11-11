"""Safely refresh one static issue, retaining published data on failure."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import build_site_payload
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
    if re.search(r"政策|新政|费用|收费|物流|延误|合规|风险|监管|规则|授权|专利|policy|fees?|shipping|logistics|IOSS|关税|海关", title, re.I):
        return "watch"
    if re.search(r"工具|方法|指南|如何|做法|实践|案例|破局|复盘|经验|MCF|ASIN|QA|build|guide|workflow", title, re.I):
        return "learn"
    if re.search(r"发布|宣布|推出|上线|重大|改革|announc|launch|introduc", title, re.I):
        return "news"
    return None


def amazon_impact(article: dict, bucket: str) -> int:
    title = article.get("title", "")
    if bucket == "watch":
        if re.search(r"亚马逊.*(?:授权|政策|费用|收费|规则)", title, re.I):
            return 100
        if re.search(r"物流|延误|发货", title, re.I):
            return 90
        if re.search(r"IOSS|关税|税费", title, re.I):
            return 80
        if re.search(r"亚马逊", title) and re.search(r"上架|专利|合规", title):
            return 70
        return 30
    if bucket == "news":
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
    sources = []
    for bucket, rows in groups.items():
        rows.sort(key=lambda row: (amazon_impact(row, bucket), row.get("date", ""), row.get("title", "")), reverse=True)
        for article in rows[:3]:
            excerpt = (article.get("title", "") + "。" + article.get("summary", "")).strip()
            if len(excerpt) < 12:
                continue
            sources.append({"id": f"A{len(sources) + 1}", "title": article["title"],
                            "sourceName": article["sourceName"], "publishedAt": article["date"],
                            "url": article["sourceUrl"], "excerpt": excerpt[:2400],
                            "bucket": bucket})
    return sources


def refresh_amazon(day: date, card_client=request_cards) -> bool:
    before = json.loads((DATA / "amazon.json").read_text(encoding="utf-8"))
    update_amazon_news.main()
    path = DATA / "amazon.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = amazon_sources(payload["articles"], day)
    week = generate_weekly.week_key(monday(day))
    old_ai = before.get("ai", {})
    if old_ai.get("week") == week and old_ai.get("sources") == sources:
        cards = old_ai.get("cards", {})
    else:
        model = os.environ.get("AI_NEWS_MODEL", "deepseek-flash").strip()
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if sources and (not model or not key):
            raise RuntimeError("model credentials are not configured")
        cards = card_client(sources, model, key, amazon=True)
    payload["ai"] = {"week": week, "date": day.isoformat(), "sources": sources, "cards": cards,
                     "model": os.environ.get("AI_NEWS_MODEL", "deepseek-flash")}
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
