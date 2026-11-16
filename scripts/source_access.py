"""Reject article links whose publisher explicitly requires payment to read."""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from html import unescape
from threading import Lock
from urllib.parse import urlparse


_PAID_TEXT = re.compile(
    r"\b(?:this (?:post|article|story) is (?:only )?for paid subscribers|"
    r"become a paid subscriber to (?:continue|read)|paid subscribers only|"
    r"continue reading with a paid subscription|upgrade to paid to read the rest)\b",
    re.IGNORECASE,
)
_PAID_SCHEMA = re.compile(r'"isAccessibleForFree"\s*:\s*false\b', re.IGNORECASE)
_MEDIUM_PAYWALL = re.compile(
    r"the author made this story available to medium members only", re.IGNORECASE,
)
_UNKNOWN_ACCESS_URLS: set[str] = set()
_UNKNOWN_LOCK = Lock()


def page_requires_payment(html: str, url: str = "") -> bool:
    """Look for an explicit article paywall, not generic subscription marketing."""
    plain = unescape(html)
    host = urlparse(url).hostname or ""
    medium_article = host == "medium.com" or host.endswith(".medium.com")
    return bool(_PAID_SCHEMA.search(html) or _PAID_TEXT.search(plain)
                or (medium_article and _MEDIUM_PAYWALL.search(plain)))


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
        with _UNKNOWN_LOCK:
            _UNKNOWN_ACCESS_URLS.add(url)
        return False
    return page_requires_payment(html, url)


def log_unknown_selected(sources: list[dict]) -> None:
    """Record only unverified originals that survive into a generated issue."""
    with _UNKNOWN_LOCK:
        unknown = set(_UNKNOWN_ACCESS_URLS)
    for source in sources:
        url = source.get("sourceUrl") or source.get("url")
        if url in unknown:
            print(f"Selected original has unverified access: {url}", file=sys.stderr)


def exclude_paid_sources(items: list[dict], checker=source_requires_payment) -> list[dict]:
    """Keep source order while checking article URLs in parallel."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        paid = list(pool.map(
            lambda item: page_requires_payment(
                "\n".join(str(item.get(field) or "") for field in ("bodyText", "summary", "excerpt")),
                item.get("sourceUrl") or item.get("url") or "",
            )
            or checker(item.get("sourceUrl") or item["url"]), items
        ))
    for item, requires_payment in zip(items, paid):
        if requires_payment:
            print(f"Excluded paid original: {item.get('sourceUrl') or item.get('url')}", file=sys.stderr)
    return [item for item, requires_payment in zip(items, paid) if not requires_payment]
