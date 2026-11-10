import json
import io
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_opinion as opinion
import update_ai_news as collector


def item(name, day, suffix):
    return {
        "title": f"Article {suffix}",
        "date": day,
        "sourceName": name,
        "sourceUrl": f"https://{name.lower()}.example/{suffix}",
        "bodyText": f"{name} reports a new workflow and gives concrete observations. " * 5,
        "qualityScore": 80,
    }


def article_for(sources):
    paragraphs = []
    for source in sources[:2]:
        paragraphs.append({
            "text": "这条资料展示了一个具体的实践变化，也为我们判断其适用范围提供了独立观察。" * 4,
            "citations": [{"sourceId": source["id"], "evidence": source["excerpt"][:36]}],
        })
    return {
        "title": "从新工作流看人工智能实践的变化",
        "subtitle": "综合多个独立来源，讨论新工具如何进入实际工作，以及适用边界。",
        "sections": [
            {"heading": "变化", "paragraphs": paragraphs},
            {"heading": "判断", "paragraphs": paragraphs},
        ],
    }


class OpinionTests(unittest.TestCase):
    def setUp(self):
        self.items = [
            item("Alpha", "2026-11-09", "a1"),
            item("Alpha", "2026-11-09", "a2"),
            item("Beta", "2026-11-08", "b1"),
            item("Gamma", "2026-11-07", "g1"),
        ]

    def test_recent_selection_prioritizes_distinct_publishers(self):
        sources, days = opinion.select_sources(self.items + [item("Old", "2026-10-20", "old")], date(2026, 11, 9))
        self.assertEqual(days, 3)
        self.assertEqual([source["sourceName"] for source in sources[:3]], ["Alpha", "Beta", "Gamma"])
        self.assertNotIn("Old", {source["sourceName"] for source in sources})

    def test_publisher_date_overrides_stale_feed_timestamp(self):
        self.assertEqual(opinion.resolve_publication_date("https://simonwillison.net/2026/Nov/3/example/"), date(2026, 11, 3))
        sources, days = opinion.select_sources(self.items, date(2026, 11, 9),
            date_resolver=lambda url: date(2025, 12, 10) if url.endswith("/a1") else date(2026, 11, 4))
        self.assertEqual(days, 7)
        self.assertNotIn("https://alpha.example/a1", {source["url"] for source in sources})
        self.assertEqual(len({source["sourceName"] for source in sources}), 3)

    def test_full_text_fetch_candidates_spread_across_publishers(self):
        ranked = [item("Alpha", "2026-11-09", f"a{index}") for index in range(8)]
        ranked += [item("Beta", "2026-11-08", "b"), item("Gamma", "2026-11-07", "g")]
        selected = collector.diverse_fetch_candidates(ranked, 6)
        self.assertEqual([value["sourceName"] for value in selected[:3]], ["Alpha", "Beta", "Gamma"])

    def test_citation_must_match_exact_source_excerpt(self):
        sources, _ = opinion.select_sources(self.items, date(2026, 11, 9))
        valid = article_for(sources)
        published = opinion.validate_article(valid, sources)
        self.assertEqual(len(published["sources"]), 2)
        self.assertLessEqual(len(published["sections"][0]["paragraphs"][0]["citations"][0]["evidence"].split()), 7)
        valid["sections"][0]["paragraphs"][0]["citations"][0]["evidence"] = "An invented quotation absent from the article"
        with self.assertRaisesRegex(ValueError, "citation evidence"):
            opinion.validate_article(valid, sources)

    def test_unknown_source_is_rejected(self):
        sources, _ = opinion.select_sources(self.items, date(2026, 11, 9))
        invalid = article_for(sources)
        invalid["sections"][0]["paragraphs"][0]["citations"][0]["sourceId"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "citation evidence"):
            opinion.validate_article(invalid, sources)

    def test_model_request_uses_strict_schema_and_parses_response(self):
        sources, days = opinion.select_sources(self.items, date(2026, 11, 9))
        draft = article_for(sources)
        response = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(draft)}]}]}
        captured = []

        def urlopen(request, timeout):
            captured.append((request, timeout))
            return io.BytesIO(json.dumps(response).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=urlopen):
            self.assertEqual(opinion.request_article(sources, days, "model-test", "secret-test"), draft)
        request, timeout = captured[0]
        body = json.loads(request.data)
        self.assertEqual(timeout, 120)
        self.assertEqual(body["model"], "model-test")
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(body["text"]["format"]["schema"]["properties"]["sections"]["items"]["properties"]["paragraphs"]["items"]["properties"]["citations"]["minItems"], 1)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-test")
        self.assertEqual(request.full_url, opinion.API_URL)

    def test_deepseek_uses_its_own_endpoint_and_key_name(self):
        sources, days = opinion.select_sources(self.items, date(2026, 11, 9))
        draft = article_for(sources)
        response = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(draft)}]}]}
        captured = []

        def urlopen(request, timeout):
            captured.append(request)
            return io.BytesIO(json.dumps(response).encode("utf-8"))

        with patch.dict("os.environ", {"AI_NEWS_PROVIDER": "deepseek", "AI_NEWS_MODEL": "deepseek-flash", "DEEPSEEK_API_KEY": "test-key"}):
            with patch("urllib.request.urlopen", side_effect=urlopen):
                self.assertEqual(opinion.request_article(sources, days, "deepseek-flash", "test-key"), draft)
        self.assertEqual(captured[0].full_url, opinion.DEEPSEEK_API_URL)
        self.assertEqual(captured[0].get_header("Authorization"), "Bearer test-key")
        self.assertEqual(json.loads(captured[0].data)["reasoning"], {"effort": "none"})

        with patch.dict("os.environ", {"AI_NEWS_PROVIDER": "deepseek", "AI_NEWS_MODEL": "deepseek-flash", "DEEPSEEK_API_KEY": ""}):
            with tempfile.TemporaryDirectory() as directory:
                news = Path(directory) / "news.json"
                news.write_text(json.dumps({"updatedAt": "2026-11-09T08:00:00Z", "items": self.items}), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "DEEPSEEK_API_KEY"):
                    opinion.generate(news, Path(directory) / "opinion")

    def test_publish_and_failed_retry_preserves_last_edition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            news = root / "news.json"
            out = root / "opinion"
            news.write_text(json.dumps({"updatedAt": "2026-11-09T08:00:00Z", "items": self.items}), encoding="utf-8")

            def fake_client(sources, _days, _model, _key):
                return article_for(sources)

            with patch.dict("os.environ", {"AI_NEWS_MODEL": "test-model", "OPENAI_API_KEY": "test-key"}), \
                 patch.object(opinion, "resolve_publication_date", return_value=date(2026, 11, 9)):
                edition = opinion.generate(news, out, fake_client)
                before = (out / "latest.json").read_bytes()
                self.assertEqual(edition["editionDate"], "2026-11-09")
                self.assertEqual(json.loads((out / "status.json").read_text(encoding="utf-8"))["state"], "published")
                with self.assertRaises(ValueError):
                    opinion.generate(news, out, lambda *_: {"title": "bad"})
                self.assertEqual((out / "latest.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
