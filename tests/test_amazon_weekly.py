import json
import gzip
import io
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_amazon_weekly as weekly
import run_auto_update as updater
import update_ai_news
import update_amazon_news


class AmazonWeeklyChecks(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {"id": "A1", "title": "亚马逊授权规则更新，卖家需要核查授权时间",
             "sourceName": "雨果网", "publishedAt": "2026-11-12",
             "url": "https://example.com/one",
             "excerpt": "亚马逊授权规则更新，卖家需要核查授权时间。原文没有列出受影响的服务商名单。"},
            {"id": "A2", "title": "跨境发货遇到延误，空运排队情况有变化",
             "sourceName": "AMZ123", "publishedAt": "2026-11-12",
             "url": "https://example.com/two",
             "excerpt": "跨境发货遇到延误，空运排队情况有变化。原文没有给出恢复日期。"},
        ]
        p1 = {"text": "报道提到授权规则更新，但原文没有列出受影响的服务商名单。判断：卖家只能先核对自己的授权状态，不能推断所有服务商都会受到影响。",
              "citations": [{"sourceId": "A1", "evidence": "亚马逊授权规则更新，卖家需要核查授权时间"}]}
        p2 = {"text": "报道提到跨境发货有延误，空运排队情况发生变化。推断：依赖相同路线的卖家需要确认自己的物流安排；报道没有给出恢复日期和具体影响范围。",
              "citations": [{"sourceId": "A2", "evidence": "跨境发货遇到延误，空运排队情况有变化"}]}
        self.article = {"title": "亚马逊本周变化：授权与物流都需核对",
                        "subtitle": "两家公开来源显示，授权规则和发货时效值得卖家核查；具体范围仍需看原文。",
                        "sections": [
                            {"heading": "政策与合规", "paragraphs": [deepcopy(p1), deepcopy(p1)]},
                            {"heading": "物流与费用", "paragraphs": [deepcopy(p2), deepcopy(p2)]},
                            {"heading": "本周判断", "paragraphs": [deepcopy(p1), deepcopy(p2)]},
                        ]}

    def test_rejects_fabricated_number_or_missing_evidence(self):
        valid = weekly.validate_amazon_article(self.article, self.sources)
        self.assertEqual(valid["sections"][-1]["heading"], "本周判断")
        self.article["sections"][0]["paragraphs"][0]["text"] += "费用增加50元。"
        with self.assertRaisesRegex(ValueError, "unsupported number"):
            weekly.validate_amazon_article(self.article, self.sources)
        self.article["sections"][0]["paragraphs"][0]["text"] = self.article["sections"][0]["paragraphs"][1]["text"]
        self.article["sections"][0]["paragraphs"][0]["citations"][0]["evidence"] = "原文没有这个证据短语"
        with self.assertRaisesRegex(ValueError, "evidence"):
            weekly.validate_amazon_article(self.article, self.sources)

    def test_rejects_nonconsecutive_patents_as_a_range(self):
        sources = deepcopy(self.sources)
        sources[0]["excerpt"] += " 共5款，US D1155683 S、US D1155698 S。"
        article = deepcopy(self.article)
        article["sections"][0]["paragraphs"][0]["text"] = (
            "报道列出5款专利，专利号从US D1155683 S至US D1155698 S。"
            "判断：相关产品仍需逐项核对。")
        with self.assertRaisesRegex(ValueError, "distinct patent numbers"):
            weekly.validate_amazon_article(article, sources)

    def test_priority_sources_cannot_silently_drop_from_article(self):
        sources = deepcopy(self.sources) + [{
            "id": "A3", "title": "亚马逊FBA费用调整", "sourceName": "雨果网",
            "publishedAt": "2026-11-12", "url": "https://example.com/three",
            "evidenceScope": "body", "excerpt": "亚马逊FBA费用调整，具体金额按商品不同。"}]
        with self.assertRaisesRegex(ValueError, "omits priority sources"):
            weekly.validate_amazon_article(self.article, sources)

    def test_collector_decodes_implicit_gzip(self):
        class Response(io.BytesIO):
            def __init__(self, content):
                super().__init__(gzip.compress(content))
                self.headers = {"Content-Type": "text/html; charset=utf-8"}

        from email.message import Message
        response = Response("<html><title>文章</title></html>".encode("utf-8"))
        response.headers = Message()
        with patch.object(update_amazon_news.urllib.request, "urlopen", return_value=response):
            self.assertIn("文章", update_amazon_news.get_page("https://example.com/test"))

    def test_collector_retries_transient_listing_timeout(self):
        from email.message import Message

        response = io.BytesIO(b"<html><title>Recovered</title></html>")
        response.headers = Message()
        with patch.object(update_amazon_news.urllib.request, "urlopen",
                          side_effect=[TimeoutError("timed out"), response]) as request:
            self.assertIn("Recovered", update_amazon_news.get_page("https://example.com/test"))
        self.assertEqual(request.call_count, 2)

    def test_collector_failure_is_reportable_without_replacing_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "amazon.json"
            output.write_text('{"articles":[]}', encoding="utf-8")
            with patch.object(update_amazon_news, "OUT", output), \
                 patch.object(update_amazon_news, "SITES", [("AMZ123", "https://example.com/t", r"https://example.com/t/.*")]), \
                 patch.object(update_amazon_news, "RSS_SITES", []), \
                 patch.object(update_amazon_news, "get_page", side_effect=TimeoutError("timed out")):
                with self.assertRaisesRegex(RuntimeError, "collection incomplete"):
                    update_amazon_news.main()
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"articles": []})

    def test_closes_prior_issue_once(self):
        prior = {"week": "2026-W46", "date": "2026-11-15", "article": self.article,
                 "cards": {"news": [], "watch": [], "learn": []}, "sources": self.sources}
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory)
            weekly.close_prior_issue(prior, "2026-W47", archive)
            path = archive / "2026-W46.json"
            self.assertTrue(path.exists())
            prior["article"] = {"title": "changed"}
            weekly.close_prior_issue(prior, "2026-W47", archive)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["article"]["title"],
                             self.article["title"])

    def test_full_article_excludes_title_only_sources(self):
        sources = [{**self.sources[0], "evidenceScope": "title"},
                   {**self.sources[1], "evidenceScope": "body"}]
        seen = []

        def article_client(selected, *_args):
            seen.extend(selected)
            return {"title": "A generated article"}

        with patch.object(weekly, "validate_amazon_article", side_effect=lambda raw, _: raw):
            weekly.generate(sources, date(2026, 11, 12), "test", "test", client=article_client)
        self.assertEqual([source["id"] for source in seen], ["A2"])

    def test_monday_finalizes_prior_week_before_opening_new_one(self):
        def item(title, day, url):
            return {"title": title, "date": day, "sourceName": "AMZ123",
                    "sourceUrl": url, "summary": "卖家需要核对原文中的具体安排。"}
        old_rows = [item("亚马逊物流政策更新，卖家需留意发货", "2026-11-15", "https://example.com/old")]
        new_rows = [item("亚马逊物流规则更新，卖家需留意配送", "2026-11-16", "https://example.com/new")]
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "amazon.json").write_text(json.dumps({"articles": old_rows,
                "ai": {"week": "2026-W46", "date": "2026-11-15", "sources": [],
                       "cards": {}, "article": {"title": "old draft"}}}), encoding="utf-8")

            def collect():
                (data / "amazon.json").write_text(json.dumps({"articles": new_rows}), encoding="utf-8")

            with (patch.object(updater, "DATA", data),
                  patch.object(updater.update_amazon_news, "main", side_effect=collect),
                  patch.object(weekly, "generate", side_effect=[{"title": "final Sunday"},
                                                                 {"title": "new Monday"}]) as generated,
                  patch.dict(os.environ, {"AI_NEWS_MODEL": "test", "DEEPSEEK_API_KEY": "test"})):
                updater.refresh_amazon(date(2026, 11, 16),
                    card_client=lambda *args, **kwargs: {"news": [], "watch": [], "learn": []})
            self.assertEqual(generated.call_count, 2)
            archived = json.loads((data / "amazon-weekly" / "2026-W46.json").read_text(encoding="utf-8"))
            self.assertEqual(archived["article"]["title"], "final Sunday")
            self.assertEqual(archived["date"], "2026-11-15")
            current = json.loads((data / "amazon.json").read_text(encoding="utf-8"))["ai"]
            self.assertEqual(current["week"], "2026-W47")

    def test_aws_is_ai_source_only(self):
        self.assertIn("AWS 机器学习博客", [source["name"] for source in update_ai_news.RSS_SOURCES])
        self.assertNotIn("AWS 机器学习博客", [name for name, _ in update_amazon_news.RSS_SITES])
        catalog = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(len(catalog["amazonOfficialSources"]), 2)
        self.assertEqual(next(s for s in catalog["gradedSources"] if s["name"] == "AWS Machine Learning Blog RSS")["firstEligibleWeek"], "2026-W46")

    def test_collector_keeps_earlier_days_and_reads_article_body(self):
        previous = [{"sourceUrl": "https://example.com/monday", "date": "2026-11-09",
                     "title": "周一文章", "sourceName": "雨果网", "summary": "周一要点"}]
        fresh = [{"sourceUrl": "https://example.com/thursday", "date": "2026-11-12",
                  "title": "周四文章", "sourceName": "雨果网", "summary": "周四要点"}]
        merged = update_amazon_news.merge_week_articles(previous, fresh, date(2026, 11, 12))
        self.assertEqual({item["date"] for item in merged}, {"2026-11-09", "2026-11-12"})

        html = ('<aside><p>无关侧栏</p></aside><div class="article-detail-main">'
                '<p>授权从 SUP 迁移到 SPP，卖家以收到的通知为准。</p>'
                '<p>新授权有效期为 365 天，逾期服务商失去访问权限。</p></div>')
        body = update_amazon_news.article_body(html)
        self.assertIn("SUP", body)
        self.assertIn("365", body)
        self.assertNotIn("无关侧栏", body)

    def test_collector_accepts_beijing_publication_before_utc_midnight(self):
        instant = datetime(2026, 11, 11, 23, 30, tzinfo=timezone.utc)
        with patch.object(update_amazon_news, "datetime") as clock:
            clock.now.side_effect = lambda tz: instant.astimezone(tz)
            clock.fromisoformat.side_effect = datetime.fromisoformat
            day = update_amazon_news.article_date("AMZ123", "", {
                "article:published_time": "2026-11-12T07:10:00+08:00",
            })
        self.assertEqual(day, "2026-11-12")


if __name__ == "__main__":
    unittest.main()
