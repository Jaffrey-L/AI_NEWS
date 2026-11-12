"""Export a self-contained first-edition preview and inspectable AI cards."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    review = ROOT / "review"
    review.mkdir(exist_ok=True)
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "workspace.css").read_text(encoding="utf-8")
    payload = (ROOT / "data" / "site-payload.js").read_text(encoding="utf-8")
    app = (ROOT / "app.js").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="./workspace.css?v=4">', f"<style>\n{css}\n</style>")
    html = html.replace('<script src="./data/site-payload.js?v=4"></script>', f"<script>\n{payload}\n</script>")
    html = html.replace('<script src="./app.js?v=4" defer></script>', f"<script>\n{app}\n</script>\n<script>document.querySelector('[data-v=amazon]').click();</script>")
    if '<link rel="stylesheet"' in html or 'src="./app.js' in html:
        raise RuntimeError("Preview assets were not inlined")
    (review / "amazon-first-edition-preview.html").write_text(html, encoding="utf-8")

    amazon = json.loads((ROOT / "data" / "amazon.json").read_text(encoding="utf-8"))
    ai = amazon["ai"]
    source_map = {source["id"]: source for source in ai["sources"]}
    buckets = {}
    for bucket in ("news", "watch", "learn"):
        buckets[bucket] = [
            {
                "aiInterpretation": card["text"],
                "originals": [source_map[source_id] for source_id in card["src"]],
            }
            for card in ai["cards"][bucket]
        ]
    report = {"week": ai["week"], "model": ai["model"], "buckets": buckets}
    (review / "amazon-first-edition-cards.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
