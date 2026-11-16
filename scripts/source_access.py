"""Reject article links whose publisher explicitly requires payment to read."""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from html import unescape


_PAID_TEXT = re.compile(
    r"\b(?:this (?:post|article|story) is (?:only )?for paid subscribers|"
    r"become a paid subscriber to (?:continue|read)|paid subscribers only)\b",
    re.IGNORECASE,
)
_PAID_SCHEMA = re.compile(r'"isAccessibleForFree"\s*:\s*false\b', re.IGNORECASE)


def page_requires_payment(html: str) -> bool:
    """Look for an explicit article paywall, not generic subscription marketing."""
    return bool(_PAID_SCHEMA.search(html) or _PAID_TEXT.search(unescape(html)))


@lru_cache(maxsize=512)
def source_requires_payment(url: str) -> bool:
    """Treat fetch failures as unknown; an HTTP 403 can be a bot block."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"}
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            html = response.read(1_500_000).decode("utf-8", "replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return False
    return page_requires_payment(html)


def exclude_paid_sources(items: list[dict], checker=source_requires_payment) -> list[dict]:
    """Keep source order while checking article URLs in parallel."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        paid = list(pool.map(
            lambda item: page_requires_payment(item.get("bodyText") or item.get("summary") or "")
            or checker(item["sourceUrl"]), items
        ))
    for item, requires_payment in zip(items, paid):
        if requires_payment:
            print(f"Excluded paid original: {item['sourceUrl']}", file=sys.stderr)
    return [item for item, requires_payment in zip(items, paid) if not requires_payment]
