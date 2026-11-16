"""A paid original cannot enter an AI article as a clickable source."""

import sys
import io
import unittest
import urllib.error
from contextlib import redirect_stderr
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_access import log_unknown_selected, page_requires_payment, source_requires_payment


class SourceAccessTests(unittest.TestCase):
    def test_article_level_paid_marker_excludes_paid_post_but_keeps_free_post(self):
        paid = '<script type="application/ld+json">{"isAccessibleForFree":false}</script>'
        free = '<script type="application/ld+json">{"isAccessibleForFree":true}</script>'
        self.assertTrue(page_requires_payment(paid))
        self.assertTrue(page_requires_payment('<h2 class="paywall-title">This post is for paid subscribers</h2>'))
        self.assertFalse(page_requires_payment(free + '<a href="/subscribe">Subscribe</a>'))
        self.assertFalse(page_requires_payment("This article discusses paywalls in the industry."))
        self.assertTrue(page_requires_payment("Continue reading with a paid subscription"))
        self.assertTrue(page_requires_payment(
            "Member-only story. The author made this story available to Medium members only.",
            "https://medium.com/example/story"))
        self.assertFalse(page_requires_payment(
            "Create a free account to keep reading this article.",
            "https://medium.com/example/free-story"))
        self.assertTrue(page_requires_payment("此内容为付费阅读，请付费后查看"))
        self.assertTrue(page_requires_payment("开通会员阅读全文"))
        self.assertTrue(page_requires_payment("付费阅读完整内容"))
        self.assertTrue(page_requires_payment("VIP专享：解锁全文"))
        self.assertFalse(page_requires_payment("老板会员为邀请制，填写入会信息即可免费加入老板会员。查看完整内容请下载"))
        self.assertFalse(page_requires_payment("文章介绍平台付费阅读和会员专享服务的商业模式。"))

    def test_split_markup_and_common_chinese_paid_prompts(self):
        paid = (
            "<span>付费</span><button>阅读全文</button>",
            "VIP 专享，解锁全文",
            "成为会员即可阅读全文",
            "订阅后阅读全文",
            "剩余 80% 内容，付费后可查看",
            "本文为会员专享内容",
        )
        free = (
            "免费订阅后阅读全文",
            "成为免费会员即可阅读全文",
            '<span class="付费">本文介绍会员制商业模式</span>',
        )
        for html in paid:
            with self.subTest(paid=html):
                self.assertTrue(page_requires_payment(html))
        for html in free:
            with self.subTest(free=html):
                self.assertFalse(page_requires_payment(html))

    def test_http_403_is_unknown_not_proof_of_paid_access(self):
        url = "https://example.com/browser-readable"
        with patch("source_access.urllib.request.urlopen", side_effect=urllib.error.HTTPError(url, 403, "", {}, None)):
            self.assertFalse(source_requires_payment(url))
        output = io.StringIO()
        with redirect_stderr(output):
            log_unknown_selected([{"url": "https://example.com/other"}, {"url": url}])
        self.assertEqual(output.getvalue().count(url), 1)

    def test_publisher_page_paid_marker_is_checked(self):
        url = "https://example.com/paid-article"
        html = b'<h2 class="paywall-title">This post is for paid subscribers</h2>'
        with patch("source_access.urllib.request.urlopen", return_value=BytesIO(html)):
            self.assertTrue(source_requires_payment(url))


if __name__ == "__main__":
    unittest.main()
