import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "news.json"
SOURCES_FILE = ROOT / "sources.json"
DIGEST_DIR = ROOT / "data" / "digests"
CREATOR_CATEGORY = "\u6838\u5fc3AI\u535a\u4e3b"
PRACTICE_CATEGORY = "Vibe/Prompt/Agent\u5b9e\u6218"
SOLO_CATEGORY = "AI\u4e2a\u4eba\u516c\u53f8\u5927\u795e"
PREFERRED_QUALITY_TYPES = {"technical_update", "feature_update", "application_method"}
YEAR_START = "2026-01-01"


def main():
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    source_pool = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    archive_items = payload.get("archiveItems", [])
    top_stories = payload.get("topStories", [])
    source_health = payload.get("sourceHealth", {})
    source_health_details = payload.get("sourceHealthDetails", [])
    p0_quality = payload.get("p0Quality", {})
    coverage = payload.get("sourceCoverage", {})
    trends = payload.get("trends", {})
    digest_archive = payload.get("digestArchive", {})
    cutoff = datetime.strptime(payload.get("yearStart", YEAR_START), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    expected_sources = set(source_pool.get("companies", [])) | set(source_pool.get("creators", [])) | set(source_pool.get("soloBuilders", []))

    assert len(items) >= 40, f"expected at least 40 YTD news items, got {len(items)}"
    assert all(item.get("qualityScore", 0) >= 60 for item in items), "default feed contains items below qualityScore 60"
    assert all(item.get("qualityReview", {}).get("isDefaultVisible") for item in items), "default feed contains non-default-visible items"
    assert all(item.get("qualityScore", 0) >= 80 for item in top_stories), "top stories must be qualityScore >= 80"
    assert all(item.get("qualityReview", {}).get("isTopEligible") for item in top_stories), "top stories must be top eligible"
    assert all(item.get("qualityReview", {}).get("reasons") for item in items), "default items must include quality reasons"
    assert all(len(item.get("qualityReview", {}).get("reasons", [])) >= 2 for item in top_stories), "top stories need at least two quality reasons"
    assert isinstance(archive_items, list), "archiveItems should be present for low priority content"
    assert payload.get("coverageWindow") == "YTD", "expected year-to-date coverage window"
    assert expected_sources.issubset(set(coverage)), "source coverage is missing: {}".format(sorted(expected_sources - set(coverage)))
    assert 1 <= len(top_stories) <= 10, f"expected 1-10 top stories, got {len(top_stories)}"
    assert len({item.get("eventId") for item in top_stories}) == len(top_stories), "top stories contain duplicate event ids"
    assert source_health.get("total", 0) >= len(expected_sources), "source health does not cover all tracked sources"
    assert source_health.get("ok", 0) + source_health.get("empty", 0) >= int(source_health.get("total", 0) * 0.75), "too many source failures"
    assert isinstance(source_health_details, list) and len(source_health_details) >= len(expected_sources), "expected source health detail rows"
    assert p0_quality.get("topStoryCount") == len(top_stories), "p0 quality metadata should match top story count"
    assert p0_quality.get("defaultVisibleCount") == len(items), "default visible count mismatch"
    assert p0_quality.get("archiveCount") == len(archive_items), "archive count mismatch"
    assert trends.get("windowDays") == 7, "expected 7-day trends metadata"
    assert trends.get("itemCount", 0) > 0, "expected at least one item in trend window"
    assert isinstance(trends.get("topics"), list) and trends["topics"], "expected topic trends"
    assert isinstance(trends.get("qualityTypes"), list) and trends["qualityTypes"], "expected quality trend summary"
    digest_path = ROOT / digest_archive.get("path", "")
    latest_digest_path = ROOT / digest_archive.get("latestPath", "")
    assert digest_archive.get("date"), "expected digest archive date"
    assert digest_path.exists(), f"expected digest archive file: {digest_path}"
    assert latest_digest_path.exists(), f"expected latest digest archive file: {latest_digest_path}"
    digest_text = digest_path.read_text(encoding="utf-8")
    assert f"今日必看 Top {len(top_stories)}" in digest_text, "digest archive missing dynamic Top section"
    assert "7 天趋势雷达" in digest_text, "digest archive missing trend section"
    assert p0_quality.get("fetchedArticles", 0) >= 3, "expected at least 3 real article bodies to be fetched"
    assert any(item.get("contentFetched") for item in items), "expected fetched full-text article content"
    assert any(item.get("aggregatedEvent") for item in items), "expected at least one aggregated event card"
    assert any(item.get("sourceGrade") == "A" for item in items), "expected at least one A-grade source"
    assert any(item.get("sourceGrade") == "B" for item in items), "expected at least one B-grade source"
    assert any("enterprise" in [str(tag).lower() for tag in item.get("tags", [])] for item in items), "expected enterprise-tagged content"
    assert any(item.get("category") == PRACTICE_CATEGORY for item in items), "expected practice category content"
    assert any(item.get("category") == CREATOR_CATEGORY for item in items), "expected creator/blogger content"
    assert any(item.get("category") == SOLO_CATEGORY for item in items), "expected solo-builder content or curated solo-builder intelligence"
    assert any(row.get("category") == SOLO_CATEGORY and row.get("statusLabelZh") in {"正常", "暂无高价值内容"} for row in source_health_details), "expected visible solo-builder source health"
    assert any(item.get("sourceName") == "Andrej Karpathy" for item in items) or "Andrej Karpathy" in coverage, "expected Andrej Karpathy to be tracked"
    assert sum(1 for item in items if item.get("qualityType") in PREFERRED_QUALITY_TYPES) >= int(len(items) * 0.85), "expected most items to be high-value technical/feature/method content"
    assert any(item.get("qualityType") == "technical_update" for item in items), "expected technical update content"
    assert any(item.get("qualityType") == "feature_update" for item in items), "expected feature update content"
    assert any(item.get("qualityType") == "application_method" for item in items), "expected AI application method content"

    for item in items:
        date = datetime.strptime(item["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        assert date >= cutoff, f"item is older than 30 days: {item['title']} ({item['date']})"
        for field in ("title", "titleZh", "summary", "summaryZh", "date", "sourceName", "sourceUrl", "sourceGrade", "category", "readingScore", "qualityScore", "qualityType", "qualityLabelZh", "eventId", "intelligenceBrief"):
            assert item.get(field), f"missing field {field}: {item}"
        assert item.get("qualityReview", {}).get("reasons"), f"missing quality reasons: {item['title']}"
        brief = item.get("intelligenceBrief", {})
        for field in ("whatHappened", "whyItMatters", "takeaway", "audience", "recommendationReason"):
            assert brief.get(field), f"missing intelligence brief field {field}: {item['title']}"
        assert item["qualityType"] in PREFERRED_QUALITY_TYPES, f"low-value item leaked into feed: {item['title']} ({item['qualityType']})"
        assert item["qualityScore"] >= 30, f"quality score too low: {item['title']} ({item['qualityScore']})"
        assert len(item["summary"]) >= 40, f"summary is too short: {item['title']}"
        assert len(item["summaryZh"]) >= 40, f"Chinese summary is too short: {item['title']}"
        assert "近 30 天" not in item["summaryZh"], f"stale 30-day copy leaked into summary: {item['title']}"
        assert isinstance(item.get("keyPoints"), list) and item["keyPoints"], f"missing key points: {item['title']}"
        assert isinstance(item.get("keyPointsZh"), list) and item["keyPointsZh"], f"missing Chinese key points: {item['title']}"
        assert not any("Worth reading for practical context" in point for point in item.get("keyPointsZh", [])), f"untranslated key point: {item['title']}"
        assert not any("近 30 天" in point for point in item.get("keyPointsZh", [])), f"stale 30-day copy leaked into key points: {item['title']}"

    print(
        "PASS news data validation: "
        f"{len(items)} items, "
        f"{len(coverage)}/{len(expected_sources)} tracked sources covered, "
        f"{sum(1 for i in items if i['sourceGrade'] == 'A')} A-grade, "
        f"{sum(1 for i in items if i['category'] == CREATOR_CATEGORY)} creator items, "
        f"{sum(1 for i in items if i['category'] == PRACTICE_CATEGORY)} practice items, "
        f"{sum(1 for i in items if i['category'] == SOLO_CATEGORY)} solo-builder items, "
        f"{sum(1 for i in items if i['qualityType'] == 'technical_update')} technical, "
        f"{sum(1 for i in items if i['qualityType'] == 'feature_update')} feature, "
        f"{sum(1 for i in items if i['qualityType'] == 'application_method')} method."
        f" Top stories: {len(top_stories)}. "
        f"Source health: {source_health.get('ok')}/{source_health.get('total')} ok, "
        f"{source_health.get('empty', 0)} empty. "
        f"Curated sources: {source_health.get('curated', 0)}. "
        f"Fetched article bodies: {p0_quality.get('fetchedArticles')}."
        f" Trends: {trends.get('itemCount')} items from {trends.get('startDate')} to {trends.get('endDate')}. "
        f"Digest: {digest_archive.get('path')}."
    )


if __name__ == "__main__":
    main()
