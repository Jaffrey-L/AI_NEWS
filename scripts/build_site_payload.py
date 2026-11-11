"""Build the static reader payload from published editions and verified sources."""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    index = read(DATA / "weekly" / "index.json")
    cards = read(DATA / "editorial-cards.json")
    sources = read(ROOT / "sources.json")
    amazon = read(DATA / "amazon.json")
    weeks = []
    for entry in index["weeks"]:
        doc = read(ROOT / entry["path"])
        week = {**doc, "week": entry["week"], "weekStart": entry["weekStart"], "weekEnd": entry["weekEnd"]}
        selection = doc.get("cards") or ({key: doc[key] for key in ("news", "watch", "learn")}
                                         if all(key in doc for key in ("news", "watch", "learn")) else None)
        if selection is None:
            selection = cards.get(entry["week"])
        if selection is None:
            excerpts = [p["text"] for section in doc.get("sections", []) for p in section.get("paragraphs", []) if p.get("text")]
            selection = {"news": [{"text": text, "src": list(dict.fromkeys(c["sourceId"] for c in p.get("citations", [])))} for section in doc.get("sections", []) for p in section.get("paragraphs", []) if p.get("text")][:3], "watch": [], "learn": []}
        for key in ("news", "watch", "learn"):
            week[key] = selection.get(key, [])
        weeks.append(week)
    counts = Counter(item.get("sourceName") for week in weeks for item in week.get("sources", []))
    direct = []
    query = []
    name_map = {
        "OpenAI News RSS": "OpenAI",
        "Google DeepMind Blog RSS": "Google DeepMind",
        "Google AI Blog RSS": "Google AI",
        "Google Research Blog RSS": "Google Research",
        "NVIDIA AI Blog RSS": "NVIDIA",
        "Mistral AI RSS": "Mistral AI",
        "Hugging Face Blog RSS": "Hugging Face",
        "Andrej Karpathy Blog RSS": "Andrej Karpathy",
        "One Useful Thing RSS": "Ethan Mollick",
    }
    for source in sources["gradedSources"]:
        name = name_map.get(source["name"], source["name"].replace(" RSS", "").replace(" Atom", ""))
        entry = {"feed": source["name"], "sourceName": name, "url": source["url"], "cited": counts.get(name, 0)}
        (direct if source["grade"] == "A" else query).append(entry)
    payload = {
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "weeks": weeks,
        "amazon": amazon,
        "updateStatus": read(DATA / "update-status.json") if (DATA / "update-status.json").exists() else {},
        "srcStatus": {
            "direct": direct,
            "query": query,
            "pending": [
                {"name": "社交平台原帖", "group": "社交平台", "what": "已接入对应公开网站文章；社交平台原帖尚未直接采集。", "why": "本站按文章实际所在网站标注出处。"},
                {"name": "X 动态", "group": "X", "what": "付费 X 接口未启用。", "why": "项目保持零新增服务费用。"},
            ],
            "catalog": {key: sources[key] for key in ("companies", "creators", "soloBuilders")},
            "cited": [{"name": name, "count": count} for name, count in counts.items() if name],
            "amazonSources": sources["amazonSources"],
            "amazonOfficialSources": sources["amazonOfficialSources"],
        },
    }
    target = DATA / "site-payload.js"
    target.write_text("window.AI_NEWS_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"weeks={len(weeks)} direct={len(direct)} amazon={len(amazon['articles'])} bytes={target.stat().st_size}")


if __name__ == "__main__":
    main()
