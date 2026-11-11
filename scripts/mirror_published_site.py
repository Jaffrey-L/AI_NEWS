"""Mirror the published static AI_NEWS site to the original Linux host.

The public GitHub Pages build is the single publishing source. A failed or
incomplete fetch never changes the currently served release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

BASE_URL = "https://jaffrey-l.github.io/AI_NEWS/"
ROOT = Path("/var/www/ai-news-mirror")
FILES = ("index.html", "workspace.css", "app.js", "data/site-payload.js")
MAX_FILE_BYTES = 3_000_000


def fetch_file(base_url: str, name: str) -> bytes:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/" + name,
        headers={"User-Agent": "AI_NEWS original-site mirror", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError(f"{name} returned HTTP {response.status}")
        content = response.read(MAX_FILE_BYTES + 1)
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError(f"{name} has an invalid size")
    return content


def validate(files: dict[str, bytes]) -> None:
    index = files["index.html"]
    for reference in (b"workspace.css", b"app.js", b"data/site-payload.js"):
        if reference not in index:
            raise ValueError(f"index.html does not reference {reference.decode()}")
    if len(files["workspace.css"]) < 1000 or len(files["app.js"]) < 1000:
        raise ValueError("site assets are unexpectedly short")
    payload = files["data/site-payload.js"].decode("utf-8").strip()
    prefix = "window.AI_NEWS_DATA = "
    if not payload.startswith(prefix) or not payload.endswith(";"):
        raise ValueError("published data script has an unexpected format")
    data = json.loads(payload[len(prefix):-1])
    if not isinstance(data.get("weeks"), list) or not data["weeks"]:
        raise ValueError("published data has no weekly issues")
    if not isinstance(data.get("amazon"), dict):
        raise ValueError("published data has no Amazon section")
    if not isinstance(data.get("updateStatus"), dict):
        raise ValueError("published data has no refresh status")


def sync(base_url: str = BASE_URL, root: Path = ROOT, fetch=fetch_file) -> bool:
    files = {name: fetch(base_url, name) for name in FILES}
    validate(files)
    digest = hashlib.sha256()
    for name, content in files.items():
        digest.update(name.encode("utf-8") + b"\0" + content)
    release_name = digest.hexdigest()[:20]
    releases = root / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    release = releases / release_name
    candidate = None
    if not release.exists():
        candidate = Path(tempfile.mkdtemp(prefix=".candidate-", dir=releases))
        try:
            for name, content in files.items():
                target = candidate / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            os.replace(candidate, release)
            candidate = None
        finally:
            if candidate is not None:
                shutil.rmtree(candidate)

    current = root / "current"
    if current.is_symlink() and current.readlink() == Path("releases") / release_name:
        print(f"site mirror unchanged: {release_name}")
        return False
    if current.exists() and not current.is_symlink():
        raise ValueError("current release is not a symlink")
    staged_link = root / f".current-{release_name}"
    if staged_link.exists() or staged_link.is_symlink():
        staged_link.unlink()
    staged_link.symlink_to(Path("releases") / release_name, target_is_directory=True)
    os.replace(staged_link, current)
    print(f"site mirror updated: {release_name}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    sync(args.base_url, args.root)


if __name__ == "__main__":
    main()
