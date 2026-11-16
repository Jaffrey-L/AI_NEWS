"""A paid original cannot enter an AI article as a clickable source."""

import sys
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_access import page_requires_payment, source_requires_payment


class SourceAccessTests(unittest.TestCase):
    def test_article_level_paid_marker_excludes_paid_post_but_keeps_free_post(self):
        paid = '<script type="application/ld+json">{"isAccessibleForFree":false}</script>'
        free = '<script type="application/ld+json">{"isAccessibleForFree":true}</script>'
        self.assertTrue(page_requires_payment(paid))
        self.assertTrue(page_requires_payment('<h2 class="paywall-title">This post is for paid subscribers</h2>'))
        self.assertFalse(page_requires_payment(free + '<a href="/subscribe">Subscribe</a>'))
        self.assertFalse(page_requires_payment("This article discusses paywalls in the industry."))

    def test_http_403_is_unknown_not_proof_of_paid_access(self):
        url = "https://example.com/browser-readable"
        with patch("source_access.urllib.request.urlopen", side_effect=urllib.error.HTTPError(url, 403, "", {}, None)):
            self.assertFalse(source_requires_payment(url))

    def test_publisher_page_paid_marker_is_checked(self):
        url = "https://example.com/paid-article"
        html = b'<h2 class="paywall-title">This post is for paid subscribers</h2>'
        with patch("source_access.urllib.request.urlopen", return_value=BytesIO(html)):
            self.assertTrue(source_requires_payment(url))


if __name__ == "__main__":
    unittest.main()
