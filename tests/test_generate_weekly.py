"""The published archive must not attribute a source to the wrong week."""

import gzip
import json
import sys
import unittest
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_weekly import FEEDS, OUT_DIR, _feed_dates, openai_feed_supplement, publish_complete_week, rebuild_index, select_week_sources, week_key, week_start
from update_ai_news import RSS_SOURCES, fetch_text


class WeeklyEditionTests(unittest.TestCase):
    def test_weekly_article_retries_invalid_json_and_bad_citation_without_publishing_them(self):
        rows = [{"date": "2026-11-10", "sourceName": f"Source {i % 3}",
                 "sourceUrl": f"https://example.com/{i}", "title": f"Original {i}",
                 "bodyText": "Original source text. " * 8, "sourceGrade": "A",
                 "category": "core", "qualityScore": 80} for i in range(6)]
        rows.append({**rows[0], "sourceUrl": "https://example.com/paid", "title": "Paid original"})
        calls = []

        def article_client(sources, _days, _model, _key, instructions):
            calls.append(instructions)
            if len(calls) == 1:
                raise ValueError("model output was not valid JSON")
            evidence = "Invented source evidence" if len(calls) == 2 else "Original source text."
            return {"title": "A weekly research interpretation", "subtitle": "What changed and why it matters",
                    "sections": [{"heading": f"Section {i}", "paragraphs": [{
                        "text": "A cautious interpretation of the original research. " * 4,
                        "citations": [{"sourceId": sources[i]["id"], "evidence": evidence}]
                    }]} for i in range(2)]}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            news = root / "news.json"
            news.write_text(json.dumps({"items": rows}), encoding="utf-8")
            with patch("generate_weekly.verify_dates", return_value=rows), \
                 patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "AI_NEWS_MODEL": "deepseek-flash"}):
                published = publish_complete_week(
                    date(2026, 11, 9), news_file=news, out_dir=root / "weekly",
                    model_client=article_client,
                    access_checker=lambda url: url.endswith("/paid"),
                    card_client=lambda *_: {group: [{"src": ["S1"]}]
                                             for group in ("news", "watch", "learn")})
            self.assertTrue(published)
            self.assertEqual(len(calls), 3)
            self.assertIn("JSON schema", calls[1])
            self.assertIn("逐字复制", calls[2])
            edition = json.loads((root / "weekly" / "2026-W46.json").read_text(encoding="utf-8"))
            self.assertEqual(edition["sections"][0]["paragraphs"][0]["citations"][0]["evidence"],
                             "Original source text.")
            self.assertNotIn("https://example.com/paid", [source["url"] for source in edition["sources"]])

    def test_weekly_publication_requires_six_usable_originals_and_three_sources(self):
        rows = [{"date": "2026-11-10", "sourceName": f"Source {i % 3}",
                 "sourceUrl": f"https://example.com/{i}", "title": f"Original {i}",
                 "bodyText": "Original source text. " * 8, "sourceGrade": "A",
                 "category": "core", "qualityScore": 80} for i in range(5)]
        with TemporaryDirectory() as temp:
            root = Path(temp)
            news = root / "news.json"
            news.write_text(json.dumps({"items": rows, "sourceCoverage": {
                "The Batch": {"status": "failed: HTTP 403"}}}), encoding="utf-8")
            with patch("generate_weekly.verify_dates", return_value=rows):
                with self.assertRaisesRegex(ValueError, "fewer than six usable originals"):
                    publish_complete_week(date(2026, 11, 9), news_file=news,
                                          out_dir=root / "weekly", access_checker=lambda _: False)
            self.assertFalse((root / "weekly" / "2026-W46.json").exists())

    def test_paid_original_cannot_fill_six_article_minimum(self):
        rows = [{"date": "2026-11-10", "sourceName": f"Source {i % 3}",
                 "sourceUrl": f"https://example.com/{i}", "title": f"Original {i}",
                 "bodyText": "Original source text. " * 8} for i in range(6)]
        with TemporaryDirectory() as temp:
            root = Path(temp)
            news = root / "news.json"
            news.write_text(json.dumps({"items": rows}), encoding="utf-8")
            with patch("generate_weekly.verify_dates", return_value=rows):
                with self.assertRaisesRegex(ValueError, "fewer than six usable originals"):
                    publish_complete_week(date(2026, 11, 9), news_file=news,
                                          out_dir=root / "weekly",
                                          access_checker=lambda url: url.endswith("/0"))
            self.assertFalse((root / "weekly" / "2026-W46.json").exists())

    def test_weekly_publication_retries_missing_reader_group(self):
        rows = [{"date": "2026-11-10", "sourceName": f"Source {i % 3}",
                 "sourceUrl": f"https://example.com/{i}", "title": f"Original {i}",
                 "bodyText": "Original source text. " * 8, "sourceGrade": "A",
                 "category": "core", "qualityScore": 80} for i in range(6)]
        with TemporaryDirectory() as temp:
            root = Path(temp)
            news = root / "news.json"
            news.write_text(json.dumps({"items": rows}), encoding="utf-8")
            with patch("generate_weekly.verify_dates", return_value=rows), \
                 patch("generate_weekly.validate_article", return_value={"sources": []}), \
                 patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "AI_NEWS_MODEL": "deepseek-flash"}):
                card_client = unittest.mock.Mock(return_value={"news": [{"src": ["S1"]}],
                                                              "watch": [{"src": ["S2"]}], "learn": []})
                with self.assertRaisesRegex(ValueError, "all three reader questions"):
                    publish_complete_week(date(2026, 11, 9), news_file=news,
                                          out_dir=root / "weekly", model_client=lambda *_: {},
                                          access_checker=lambda _: False,
                                          card_client=card_client)
            self.assertEqual(card_client.call_count, 3)
            self.assertFalse((root / "weekly" / "2026-W46.json").exists())

    def test_gzip_feed_is_read_for_collection_and_date_verification(self):
        xml = b"""<rss><channel><item><title>Model research</title>
        <link>https://deepmind.google/blog/model-research/</link>
        <pubDate>Tue, 03 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>"""

        class GzipResponse(BytesIO):
            headers = {"Content-Encoding": "gzip"}

        with patch("update_ai_news.urllib.request.urlopen", return_value=GzipResponse(gzip.compress(xml))):
            self.assertIn("Model research", fetch_text("https://deepmind.google/blog/rss.xml"))
        with patch("generate_weekly.urllib.request.urlopen", return_value=GzipResponse(gzip.compress(xml))):
            self.assertEqual(_feed_dates("Google DeepMind", "https://deepmind.google/blog/rss.xml"),
                             {"https://deepmind.google/blog/model-research": "2026-11-03"})

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
