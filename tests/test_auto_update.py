import json
import io
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_auto_update as updater
from generate_cards import request_cards, select_amazon_card_sources, validate_cards


class CardChecks(unittest.TestCase):
    def setUp(self):
        self.source = {"id": "A1", "url": "https://example.com/original", "bucket": "watch",
                       "title": "The seller fee changed on Wednesday",
                       "excerpt": "The seller fee changed on Wednesday for every merchant."}
        self.card = {"text": "平台费用变化需要卖家核对新收费表。", "sourceId": "A1",
                     "evidence": "seller fee changed on Wednesday"}

    def test_accepts_matching_original(self):
        self.assertEqual(validate_cards({"news": [], "watch": [self.card], "learn": []},
                                        [self.source])["watch"][0]["src"], ["A1"])

    def test_rejects_wrong_bucket_and_fabricated_quote(self):
        with self.assertRaises(ValueError):
            validate_cards({"news": [self.card], "watch": [], "learn": []}, [self.source])
        with self.assertRaises(ValueError):
            validate_cards({"news": [], "watch": [{**self.card, "evidence": "a quote not present anywhere"}],
                            "learn": []}, [self.source])

    def test_rejects_missing_link_and_overflow(self):
        with self.assertRaises(ValueError):
            validate_cards({"news": [], "watch": [self.card], "learn": []},
                           [{**self.source, "url": "http://example.com"}])
        with self.assertRaises(ValueError):
            validate_cards({"news": [], "watch": [self.card] * 4, "learn": []}, [self.source])

    def test_rejects_invented_number_advice_and_changed_scope(self):
        source = {**self.source, "excerpt": "亚马逊不受小包税费政策直接影响，销售额接近10%。"}
        bad = [
            "亚马逊受影响较小，销售额接近10%。",
            "亚马逊不受小包税费政策直接影响，销售额达到20%。",
            "建议卖家提前调整价格应对政策。",
        ]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_cards({"news": [], "watch": [{**self.card, "text": text,
                    "evidence": source["excerpt"]}], "learn": []}, [source])

    def test_invalid_evidence_gets_one_regeneration_before_publication(self):
        def response(evidence):
            return io.BytesIO(json.dumps({"status": "completed", "output": [{"content": [
                {"type": "output_text", "text": json.dumps({"news": [], "watch": [
                    {**self.card, "evidence": evidence}], "learn": []})}]}]}).encode("utf-8"))

        with patch("generate_cards.urllib.request.urlopen", side_effect=[
            response("not present in the source"), response(self.source["title"]),
        ]) as model_request:
            cards = request_cards([self.source], "deepseek-flash", "test-key", amazon=True)
        self.assertEqual(cards["watch"][0]["src"], ["A1"])
        self.assertEqual(model_request.call_count, 2)

        with patch("generate_cards.urllib.request.urlopen", side_effect=[
            response("not present in the source"), response("still not present"),
            response("still not present"),
        ]) as model_request:
            with self.assertRaises(ValueError):
                request_cards([self.source], "deepseek-flash", "test-key", amazon=True)
        self.assertEqual(model_request.call_count, 3)

    def test_unsupported_number_gets_specific_retry_feedback(self):
        def response(text):
            return io.BytesIO(json.dumps({"status": "completed", "output": [{"content": [
                {"type": "output_text", "text": json.dumps({"news": [], "watch": [
                    {**self.card, "text": text}], "learn": []})}]}]}).encode("utf-8"))

        with patch("generate_cards.urllib.request.urlopen", side_effect=[
            response("报道说卖家费用提高 20%，具体以原文为准"),
            response("报道说卖家费用规则发生变化，具体以原文为准"),
        ]) as model_request:
            request_cards([self.source], "deepseek-flash", "test-key", amazon=True)
        retry_body = json.loads(model_request.call_args_list[1].args[0].data)
        self.assertIn("card introduces a number absent from source", retry_body["instructions"])

    def test_amazon_watch_cards_prioritize_deadlines_and_logistics(self):
        titles = ["秘鲁拟调整进口门槛", "黑五 Deal 提报截止时间", "深圳 APEC 发货管控",
                  "亚马逊旺季连更两项利好政策", "IOSS 长期改革"]
        sources = [{"id": f"A{i}", "title": title, "bucket": "watch",
                    "evidenceScope": "body", "excerpt": title}
                   for i, title in enumerate(titles, 1)]
        selected = select_amazon_card_sources(sources)
        self.assertEqual([source["id"] for source in selected], ["A2", "A3", "A4"])

    def test_amazon_compliance_precedes_other_watch_items(self):
        titles = ["亚马逊旺季连更两项利好政策", "黑五Deal提报截止",
                  "深圳APEC发货延误", "亚马逊日本站和澳大利亚站带电产品合规要求更新"]
        sources = [{"id": f"A{i}", "title": title, "bucket": "watch",
                    "evidenceScope": "body", "excerpt": title}
                   for i, title in enumerate(titles, 1)]
        selected = select_amazon_card_sources(sources)
        self.assertEqual([source["id"] for source in selected], ["A2", "A3", "A4"])

    def test_amazon_cards_keep_distinct_valid_sources_across_attempts(self):
        sources = [{"id": name, "title": f"{name} original source title", "bucket": bucket,
                    "evidenceScope": "body", "url": f"https://example.com/{name}",
                    "excerpt": f"{name} original source title and detailed reporting."}
                   for name, bucket in [("A1", "news"), ("A2", "watch"),
                                        ("A3", "watch"), ("A4", "learn")]]

        def card(name):
            return {"sourceId": name, "text": f"{name}原站报道了相关变化，详情应以原文为准。",
                    "evidence": f"{name} original source title"}

        def response(groups):
            return io.BytesIO(json.dumps({"status": "completed", "output": [{"content": [
                {"type": "output_text", "text": json.dumps(groups)}]}]}).encode("utf-8"))

        first = {"news": [card("A1"), card("A1")],
                 "watch": [card("A2"), card("A2")], "learn": [card("A4")]}
        second = {"news": [card("A1")], "watch": [card("A3")], "learn": []}
        with patch("generate_cards.urllib.request.urlopen", side_effect=[
            response(first), response(second),
        ]) as model_request:
            cards = request_cards(sources, "deepseek-flash", "test-key", amazon=True)
        self.assertEqual([item["src"] for item in cards["watch"]], [["A2"], ["A3"]])
        self.assertEqual([item["src"] for item in cards["news"]], [["A1"]])
        self.assertEqual(model_request.call_count, 2)


class SafeRefresh(unittest.TestCase):
    def test_failure_restores_content_and_records_shown_week(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data"
            (data / "weekly").mkdir(parents=True)
            (data / "weekly" / "index.json").write_text(
                json.dumps({"weeks": [{"week": "2026-W45"}]}), encoding="utf-8")
            news = data / "news.json"
            news.write_text('{"old":true}', encoding="utf-8")

            def fail():
                news.write_text('{"new":true}', encoding="utf-8")
                raise RuntimeError("source unavailable")

            with patch.object(updater, "DATA", data), patch.object(updater.build_site_payload, "main"):
                self.assertFalse(updater.run("weekly", date(2026, 11, 16), ai_refresh=fail))
            self.assertEqual(json.loads(news.read_text(encoding="utf-8")), {"old": True})
            status = json.loads((data / "update-status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["weekly"]["shownWeek"], "2026-W45")
            self.assertEqual(status["weekly"]["attemptedWeek"], "2026-W46")

    def test_amazon_collection_failure_keeps_issue_and_marks_update_failed(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data"
            data.mkdir()
            amazon = data / "amazon.json"
            original = {"updatedAt": "2026-11-12T04:02:22Z",
                        "ai": {"week": "2026-W46"}, "articles": [{"title": "old"}]}
            amazon.write_text(json.dumps(original), encoding="utf-8")

            def fail(_day):
                amazon.write_text('{"articles":[]}', encoding="utf-8")
                raise RuntimeError("Amazon source collection incomplete")

            with patch.object(updater, "DATA", data), patch.object(updater.build_site_payload, "main"):
                self.assertFalse(updater.run("amazon", date(2026, 11, 13), amazon_refresh=fail))
            self.assertEqual(json.loads(amazon.read_text(encoding="utf-8")), original)
            status = json.loads((data / "update-status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["amazon"]["state"], "failed")
            self.assertEqual(status["amazon"]["shownWeek"], "2026-W46")

    def test_amazon_policies_exclude_technical_and_watch_fees(self):
        self.assertIsNone(updater.amazon_bucket({"sourceName": "AWS 机器学习博客", "title": "New model"}))
        self.assertEqual(updater.amazon_bucket({"sourceName": "AMZ123", "title": "亚马逊物流费用新政"}), "watch")
        self.assertEqual(updater.amazon_bucket({"sourceName": "雨果网", "title": "亚马逊黑五网一攻略：Deal提报截止汇总"}), "watch")
        self.assertEqual(updater.amazon_bucket({"sourceName": "雨果网", "title": "亚马逊重型大件难做？三招破局"}), "learn")

    def test_amazon_direct_seller_action_outweighs_other_platform_news(self):
        articles = [
            {"sourceName": "AMZ123", "title": "欧盟小包新政冲击Temu", "date": "2026-11-11", "sourceUrl": "https://example.com/other", "summary": "行业消息"},
            {"sourceName": "雨果网", "title": "亚马逊服务商授权升级，年底前重新授权", "date": "2026-11-11", "sourceUrl": "https://example.com/auth", "summary": "操作变更"},
            {"sourceName": "AMZ123", "title": "欧盟IOSS关税改革", "date": "2026-11-11", "sourceUrl": "https://example.com/ioss", "summary": "门槛变化"},
            {"sourceName": "AMZ123", "title": "深圳物流延误影响发货", "date": "2026-11-11", "sourceUrl": "https://example.com/logistics", "summary": "运输变化"},
        ]
        with patch.object(updater.update_amazon_news, "fetch_article", return_value=None):
            watch = [source["url"] for source in updater.amazon_sources(articles, date(2026, 11, 11))]
        self.assertEqual(watch[:3], ["https://example.com/auth", "https://example.com/logistics", "https://example.com/ioss"])
        self.assertIn("https://example.com/other", watch)

    def test_amazon_reranks_whole_week_and_includes_seller_case(self):
        def article(title, day, slug):
            return {"sourceName": "雨果网", "title": title, "date": day,
                    "sourceUrl": f"https://example.com/{slug}", "summary": "卖家可核对原文详情"}

        articles = [
            article("亚马逊服务商授权升级", "2026-11-09", "auth"),
            article("深圳物流延误影响发货", "2026-11-11", "logistics"),
            article("欧盟IOSS关税改革", "2026-11-11", "ioss"),
            article("亚马逊日本站和澳大利亚站带电产品合规要求更新", "2026-11-11", "compliance"),
            article("只改了一个预计送达时间，亚马逊订单当天就回来了", "2026-11-11", "case"),
        ]
        with patch.object(updater.update_amazon_news, "fetch_article", return_value=None):
            sources = updater.amazon_sources(articles, date(2026, 11, 11))
        self.assertEqual([source["url"] for source in sources if source["bucket"] == "news"],
                         ["https://example.com/auth"])
        self.assertEqual([source["url"] for source in sources if source["bucket"] == "watch"],
                         ["https://example.com/compliance", "https://example.com/logistics",
                          "https://example.com/ioss"])
        self.assertEqual([source["url"] for source in sources if source["bucket"] == "learn"],
                         ["https://example.com/case"])
        self.assertIn("https://example.com/ioss", [source["url"] for source in sources])

    def test_amazon_keeps_earlier_day_even_with_many_newer_watch_items(self):
        articles = [{"sourceName": "AMZ123", "title": f"亚马逊物流延误提醒{i}",
                     "date": "2026-11-11", "sourceUrl": f"https://example.com/new{i}",
                     "summary": "发货安排"} for i in range(12)]
        articles.append({"sourceName": "AMZ123", "title": "亚马逊物流延误旧日提醒",
                         "date": "2026-11-09", "sourceUrl": "https://example.com/monday",
                         "summary": "发货安排"})
        with patch.object(updater.update_amazon_news, "fetch_article", return_value=None):
            sources = updater.amazon_sources(articles, date(2026, 11, 12))
        self.assertIn("https://example.com/monday", [source["url"] for source in sources])

    def test_amazon_body_evidence_includes_title_for_cards(self):
        article = {"sourceName": "AMZ123", "title": "亚马逊授权规则更新",
                   "date": "2026-11-12", "sourceUrl": "https://example.com/auth",
                   "bodyText": "The seller must complete a new authorization. " * 3}
        sources = updater.amazon_sources([article], date(2026, 11, 12))
        self.assertEqual(len(sources), 1)
        self.assertTrue(sources[0]["excerpt"].startswith(article["title"] + "\n"))
        self.assertIn("The seller must complete", sources[0]["excerpt"])

    def test_amazon_preserves_a_practical_case_when_alerts_fill_the_limit(self):
        articles = [
            {"sourceName": "AMZ123", "title": f"亚马逊物流费用调整提醒{i}",
             "date": "2026-11-11" if i == 0 else "2026-11-13",
             "sourceUrl": f"https://example.com/watch{i}",
             "summary": "卖家费用提醒", "bodyText": "The source article describes seller fees. " * 4}
            for i in range(20)
        ]
        articles.append({"sourceName": "雨果网／雨果跨境",
                         "title": "亚马逊重型大件难做？Humhold用三招破局",
                         "date": "2026-11-11", "sourceUrl": "https://example.com/case",
                         "summary": "卖家案例", "bodyText": "The source article describes a practical seller method. " * 4})

        sources = updater.amazon_sources(articles, date(2026, 11, 13))
        self.assertLessEqual(len(sources), 15)
        self.assertIn("https://example.com/case", [item["url"] for item in sources])
        self.assertEqual(next(item["bucket"] for item in sources if item["url"] == "https://example.com/case"), "learn")


if __name__ == "__main__":
    unittest.main()
