"""The published archive must not attribute a source to the wrong week."""

import json
import sys
import unittest
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_weekly import FEEDS, OUT_DIR, openai_feed_supplement, rebuild_index, select_week_sources, week_key, week_start
from update_ai_news import RSS_SOURCES


class WeeklyEditionTests(unittest.TestCase):
    def test_weekly_date_verification_uses_collector_feeds(self):
        self.assertEqual(FEEDS, {source["name"]: source["url"] for source in RSS_SOURCES})
        catalog = json.loads((Path(__file__).resolve().parents[1] / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(set(FEEDS.values()),
                         {source["url"] for source in catalog["gradedSources"] if source["grade"] == "A"})

    def test_official_feed_supplement_stays_in_an_anchored_week(self):
        feed = b"""<rss><channel>
        <item><title>Agent research</title><link>https://openai.com/index/agent-research/</link>
        <pubDate>Tue, 03 Nov 2026 12:00:00 GMT</pubDate>
        <description>Research about agents and evaluations with enough source text to support a cautious weekly interpretation.</description></item>
        <item><title>Another week</title><link>https://openai.com/index/another-week/</link>
        <pubDate>Tue, 27 Oct 2026 12:00:00 GMT</pubDate>
        <description>Research about agents and evaluations with enough source text to support a cautious weekly interpretation.</description></item>
        </channel></rss>"""
        with patch("generate_weekly.urllib.request.urlopen", return_value=BytesIO(feed)):
            rows = openai_feed_supplement({"2026-W45"})
        self.assertEqual([row["sourceUrl"] for row in rows],
                         ["https://openai.com/index/agent-research/"])
        self.assertEqual(rows[0]["date"], "2026-11-03")

    def test_iso_week_spans_year_boundary(self):
        self.assertEqual(week_start(date(2026, 1, 1)), date(2025, 12, 29))
        self.assertEqual(week_key(date(2025, 12, 29)), "2026-W01")

    def test_sources_are_selected_only_from_that_week(self):
        items = [
            {"date": "2026-11-08", "sourceName": "OpenAI", "sourceGrade": "A",
             "category": "核心AI公司新闻", "sourceUrl": "https://openai.com/one",
             "title": "One", "bodyText": "A" * 90},
            {"date": "2026-11-02", "sourceName": "Simon Willison", "sourceGrade": "A",
             "category": "核心AI博主", "sourceUrl": "https://simonwillison.net/two",
             "title": "Two", "bodyText": "B" * 90},
            {"date": "2026-11-09", "sourceName": "OpenAI", "sourceGrade": "A",
             "category": "核心AI公司新闻", "sourceUrl": "https://openai.com/three",
             "title": "Three", "bodyText": "C" * 90},
        ]
        sources = select_week_sources(items, date(2026, 11, 2))
        self.assertEqual({item["sourceName"] for item in sources}, {"OpenAI", "Simon Willison"})
        self.assertTrue(all("2026-11-02" <= item["publishedAt"] <= "2026-11-08" for item in sources))

    def test_published_editions_have_original_links_and_cited_paragraphs(self):
        index = json.loads((OUT_DIR / "index.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(index["weeks"]), 2)
        for entry in index["weeks"]:
            article = json.loads((OUT_DIR / f"{entry['week']}.json").read_text(encoding="utf-8"))
            self.assertNotIn("Included for AI tracking", json.dumps(article))
            self.assertNotIn("open the original article to verify details", json.dumps(article))
            self.assertEqual(article["week"], entry["week"])
            self.assertEqual(article["weekStart"], entry["weekStart"])
            self.assertEqual(article["weekEnd"], entry["weekEnd"])
            self.assertGreaterEqual(len({s["sourceName"] for s in article["sources"]}), 2)
            source_ids = {s["id"] for s in article["sources"]}
            for source in article["sources"]:
                self.assertTrue(source["url"].startswith("https://"))
                self.assertLessEqual(entry["weekStart"], source["publishedAt"])
                self.assertLessEqual(source["publishedAt"], entry["weekEnd"])
            for section in article["sections"]:
                for paragraph in section["paragraphs"]:
                    self.assertTrue(paragraph["citations"])
                    self.assertTrue(all(c["sourceId"] in source_ids for c in paragraph["citations"]))

    def test_index_uses_only_existing_editions(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "2026-W45.json").write_text(json.dumps({
                "week": "2026-W45", "weekStart": "2026-11-02", "weekEnd": "2026-11-08",
                "title": "A", "subtitle": "B", "sources": [{"id": "S1"}]
            }), encoding="utf-8")
            index = rebuild_index(folder)
            self.assertEqual([entry["week"] for entry in index["weeks"]], ["2026-W45"])


if __name__ == "__main__":
    unittest.main()
