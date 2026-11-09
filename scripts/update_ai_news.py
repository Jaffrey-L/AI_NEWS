import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "data" / "news.json"
SOURCES_FILE = ROOT / "sources.json"
DIGEST_DIR = ROOT / "data" / "digests"

CORE_CATEGORY = "\u6838\u5fc3AI\u516c\u53f8\u65b0\u95fb"
CREATOR_CATEGORY = "\u6838\u5fc3AI\u535a\u4e3b"
SOLO_CATEGORY = "AI\u4e2a\u4eba\u516c\u53f8\u5927\u795e"
PRACTICE_CATEGORY = "Vibe/Prompt/Agent\u5b9e\u6218"
YEAR_START = "2026-01-01"
MAX_ITEMS = 500
ARTICLE_FETCH_LIMIT = 12
RSS_WORKERS = 6
GOOGLE_WORKERS = 10
ARTICLE_WORKERS = 6
MIN_QUALITY_SCORE = 30
DEFAULT_QUALITY_SCORE = 60
TOP_QUALITY_SCORE = 80

RSS_SOURCES = [
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml", "category": CORE_CATEGORY, "tags": ["OpenAI", "official"], "importance": 5},
    {"name": "NVIDIA", "url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/", "category": CORE_CATEGORY, "tags": ["NVIDIA", "official"], "importance": 4},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml", "category": PRACTICE_CATEGORY, "tags": ["Hugging Face", "open-source", "practice"], "importance": 4},
    {"name": "Microsoft AI", "url": "https://blogs.microsoft.com/ai/feed/", "category": CORE_CATEGORY, "tags": ["Microsoft AI", "official"], "importance": 4},
    {"name": "Andrej Karpathy", "url": "https://karpathy.bearblog.dev/feed/", "category": CREATOR_CATEGORY, "tags": ["Andrej Karpathy", "vibecoding", "agent", "creator"], "importance": 5},
    {"name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/", "category": CREATOR_CATEGORY, "tags": ["Simon Willison", "llm-engineering", "creator"], "importance": 5},
    {"name": "One Useful Thing", "url": "https://www.oneusefulthing.org/feed", "category": CREATOR_CATEGORY, "tags": ["Ethan Mollick", "enterprise", "creator"], "importance": 5},
    {"name": "Latent.Space", "url": "https://www.latent.space/feed", "category": CREATOR_CATEGORY, "tags": ["swyx", "agent", "creator"], "importance": 5},
    {"name": "Interconnects", "url": "https://www.interconnects.ai/feed", "category": CREATOR_CATEGORY, "tags": ["Nathan Lambert", "research", "creator"], "importance": 5},
    {"name": "The Batch", "url": "https://www.deeplearning.ai/the-batch/feed/", "category": CREATOR_CATEGORY, "tags": ["deeplearning.ai", "newsletter", "creator"], "importance": 4},
    {"name": "Chip Huyen", "url": "https://huyenchip.com/feed.xml", "category": CREATOR_CATEGORY, "tags": ["Chip Huyen", "ml-systems", "creator"], "importance": 4},
    {"name": "Lilian Weng", "url": "https://lilianweng.github.io/index.xml", "category": CREATOR_CATEGORY, "tags": ["Lilian Weng", "agent", "research"], "importance": 4},
]

EXTRA_QUERIES = [
    ("Cursor", "Cursor AI coding agent", PRACTICE_CATEGORY, ["Cursor", "coding", "agent"], 4),
    ("Claude Code", "Claude Code agent coding workflow", PRACTICE_CATEGORY, ["Claude Code", "coding", "agent"], 4),
    ("Vibe Coding", "vibe coding agent prompt engineering", PRACTICE_CATEGORY, ["vibecoding", "prompt", "agent"], 5),
    ("Enterprise Agents", "enterprise AI agent workflow deployment", PRACTICE_CATEGORY, ["enterprise", "agent", "workflow"], 5),
    ("Pieter Levels", "Pieter Levels Photo AI indie maker automation", SOLO_CATEGORY, ["Pieter Levels", "solo-builder", "Photo AI", "ai-startup"], 5),
    ("Marc Lou", "Marc Lou ShipFast AI startup build in public", SOLO_CATEGORY, ["Marc Lou", "solo-builder", "ShipFast", "workflow"], 5),
    ("Danny Postma", "Danny Postma HeadshotPro AI indie maker", SOLO_CATEGORY, ["Danny Postma", "solo-builder", "HeadshotPro", "ai-startup"], 5),
    ("Tony Dinh", "Tony Dinh Typing Mind AI indie maker", SOLO_CATEGORY, ["Tony Dinh", "solo-builder", "Typing Mind", "ai-startup"], 5),
]

CURATED_SOLO_ITEMS = [
    {
        "title": "Danny Postma: The Indie Maker Building Profitable Internet Products",
        "date": "2026-03-10",
        "sourceName": "Danny Postma",
        "sourceUrl": "https://startupik.com/danny-postma-the-indie-maker-building-profitable-internet-products/",
        "publisher": "Startupik",
        "tags": ["Danny Postma", "solo-builder", "HeadshotPro", "ai-startup", "case study"],
        "body": "Danny Postma is profiled as an indie maker building profitable internet products including AI-powered visual products such as HeadshotPro and ProfilePicture.AI. The article highlights bootstrapping, building in public, distribution, fast product iteration, automation, and portfolio strategy as practical lessons for one-person AI businesses.",
    },
    {
        "title": "The ShipFast Guide to Building in Public: How to Grow a Distribution Engine",
        "date": "2026-03-15",
        "sourceName": "Marc Lou",
        "sourceUrl": "https://stormy.ai/blog/shipfast-guide-building-in-public-distribution",
        "publisher": "Stormy AI",
        "tags": ["Marc Lou", "solo-builder", "ShipFast", "build-in-public", "workflow"],
        "body": "Marc Lou and ShipFast are used as a case study for building in public, founder distribution, and turning repeatable startup workflow into a product. The article is useful for AI builders because distribution, shipping cadence, and reusable workflow assets increasingly decide whether solo AI products can reach users.",
    },
]

BLOCKED_TITLE_KEYWORDS = ["lawsuit", "shoot", "celebrity", "stock price prediction", "price target"]
LOW_VALUE_SIGNALS = [
    "award", "awards", "conference", "event", "webinar", "podcast", "interview", "quote", "quoting",
    "workforce reduction", "hiring", "appointed", "joins", "stock", "shares", "funding", "raises",
    "partnership announced", "press release", "opinion", "policy statement",
    "government digital service", "public sector", "nhs", "vulnerability reported", "open source repositories",
]
LOW_VALUE_TITLE_SIGNALS = [
    "quoting ", "quote ", "workforce reduction", "breaking my brain", "chemical hygiene",
    "animals vs ghosts", "podcast", "interview", "event recap", "conference recap",
]
QUALITY_SIGNALS = {
    "technical_update": [
        "api", "sdk", "model", "benchmark", "architecture", "inference", "training", "eval", "evaluation",
        "embedding", "embeddings", "reasoning", "context window", "multimodal", "tool use", "function calling",
        "open weights", "fine-tuning", "dataset", "latency", "throughput", "memory", "token", "rlhf",
        "distillation", "rag", "retrieval", "vector", "agent", "agents", "computer use", "code", "coding",
    ],
    "feature_update": [
        "launch", "launches", "released", "release", "introduces", "announces", "adds", "available",
        "rollout", "beta", "general availability", "ga", "upgrade", "new feature", "connector",
        "integration", "enterprise", "workspace", "assistant", "copilot", "deep research", "operator",
    ],
    "application_method": [
        "how to", "guide", "tutorial", "workflow", "playbook", "case study", "best practice", "lessons",
        "implementation", "build", "building", "deploy", "deployment", "prompt", "prompting",
        "vibe coding", "agent workflow", "automation", "use case", "practical", "hands-on",
        "indie maker", "solo builder", "build in public", "bootstrapping", "bootstrapped", "distribution",
        "profitable internet products", "one-person", "founder workflow", "shipfast", "headshotpro", "photo ai",
    ],
}
AI_CONTEXT_TERMS = [
    "ai", "llm", "gpt", "claude", "gemini", "grok", "deepseek", "qwen", "agent", "agents",
    "prompt", "prompting", "model", "models", "openai", "anthropic", "cursor", "vibe coding",
    "machine learning", "neural", "inference", "token", "tokens", "rag", "embedding", "embeddings",
    "eval", "benchmark", "multimodal", "computer use", "tool use",
]
OFFICIAL_ALLOWED_SIGNALS = [
    "model", "models", "api", "sdk", "agent", "agents", "enterprise", "workspace", "product",
    "feature", "launch", "release", "available", "connector", "integration", "reasoning",
    "multimodal", "embedding", "fine-tuning", "deep research", "operator", "codex", "inference",
]
DEPTH_SIGNALS = [
    "how to", "guide", "tutorial", "playbook", "case study", "architecture", "benchmark",
    "evaluation", "eval", "implementation", "lessons", "workflow", "deep dive", "analysis",
    "prompt", "agent", "vibe coding", "coding", "llm", "rag", "tool use",
]
STRONG_AI_SIGNALS = [
    "llm", "gpt", "claude", "gemini", "grok", "deepseek", "qwen", "codex", "agent", "agents",
    "prompt", "prompting", "model", "models", "openai", "anthropic", "cursor", "vibe coding",
    "rag", "embedding", "embeddings", "eval", "benchmark", "multimodal", "computer use",
    "tool use", "function calling", "inference", "fine-tuning", "reasoning",
]
QUALITY_LABELS_ZH = {
    "technical_update": "\u6280\u672f\u66f4\u65b0",
    "feature_update": "\u91cd\u8981\u529f\u80fd\u66f4\u65b0",
    "application_method": "AI\u5e94\u7528\u65b9\u6cd5",
    "general": "\u4e00\u822c\u52a8\u6001",
}

TREND_MODEL_TERMS = [
    "GPT", "Claude", "Gemini", "Llama", "Grok", "DeepSeek", "Qwen", "通义", "豆包",
    "Hunyuan", "混元", "ERNIE", "文心", "Pangu", "盘古", "Sora", "Veo", "Imagen",
]

TREND_TOPIC_TERMS = {
    "Agent": ["agent", "agents", "operator", "computer use", "tool use"],
    "Vibe Coding": ["vibe coding", "coding", "code", "cursor", "claude code"],
    "Prompt": ["prompt", "prompting"],
    "企业应用": ["enterprise", "workspace", "deployment", "production"],
    "多模态": ["multimodal", "voice", "video", "image"],
    "开源模型": ["open-source", "open weights", "llama", "hugging face"],
    "推理能力": ["reasoning", "inference", "benchmark", "eval"],
}
ZH_TERMS = {
    "ai": "AI", "agent": "\u667a\u80fd\u4f53", "agents": "\u667a\u80fd\u4f53", "model": "\u6a21\u578b", "models": "\u6a21\u578b",
    "enterprise": "\u4f01\u4e1a\u5e94\u7528", "workflow": "\u5de5\u4f5c\u6d41", "deployment": "\u90e8\u7f72", "coding": "\u7f16\u7a0b",
    "prompt": "\u63d0\u793a\u8bcd", "open-source": "\u5f00\u6e90", "research": "\u7814\u7a76", "inference": "\u63a8\u7406",
    "training": "\u8bad\u7ec3", "voice": "\u8bed\u97f3", "video": "\u89c6\u9891", "search": "\u641c\u7d22", "official": "\u5b98\u65b9\u52a8\u6001",
    "creator": "\u535a\u4e3b\u89c2\u70b9", "practice": "\u5b9e\u6218\u65b9\u6cd5", "newsletter": "\u901a\u8baf", "vibecoding": "Vibe Coding",
}


def load_source_pool():
    data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    return {
        CORE_CATEGORY: list(data.get("companies", [])),
        CREATOR_CATEGORY: list(data.get("creators", [])),
        SOLO_CATEGORY: list(data.get("soloBuilders", [])),
    }


def fetch_text(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def google_news_rss(query):
    ytd_query = "{} after:{}".format(query, YEAR_START)
    encoded = urllib.parse.quote_plus(ytd_query)
    return "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en".format(encoded)


def clean_title(title):
    title = re.sub(r"\s+", " ", title or "").strip()
    return re.sub(r"\s+-\s+[^-]+$", "", title).strip()


def strip_html(value):
    text = re.sub(r"<(script|style).*?</\1>", " ", value or "", flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_article_text(html):
    if not html:
        return ""
    cleaned = re.sub(r"<(script|style|svg|noscript|header|footer|nav|aside).*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    blocks = re.findall(r"<(?:p|li|h2|h3)[^>]*>(.*?)</(?:p|li|h2|h3)>", cleaned, flags=re.IGNORECASE | re.DOTALL)
    result = []
    seen = set()
    for block in blocks:
        text = strip_html(block)
        lowered = text.lower()
        if not (45 <= len(text) <= 420):
            continue
        if any(skip in lowered for skip in ("cookie", "subscribe", "sign up", "privacy policy", "advertisement")):
            continue
        key = re.sub(r"\W+", "", lowered)[:90]
        if key and key not in seen:
            seen.add(key)
            result.append(text)
    return " ".join(result[:16])[:5200]


def extract_image(value):
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', value or "", flags=re.IGNORECASE)
    return match.group(1) if match else ""


def normalize_date(raw):
    if not raw:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[: len(fmt)], fmt).replace(tzinfo=timezone.utc).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def is_in_scope(date_str):
    try:
        published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    start = datetime.strptime(YEAR_START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return start <= published <= datetime.now(timezone.utc)


def is_relevant(title):
    lowered = title.lower()
    return not any(keyword in lowered for keyword in BLOCKED_TITLE_KEYWORDS)


def count_signals(text, signals):
    lowered = text.lower()
    return sum(1 for signal in signals if signal in lowered)


def has_ai_context(text):
    lowered = text.lower()
    for term in AI_CONTEXT_TERMS:
        term_lower = term.lower()
        if re.search(r"[\u4e00-\u9fff]", term_lower):
            if term_lower in lowered:
                return True
            continue
        pattern = r"(?<![a-z0-9]){}(?![a-z0-9])".format(re.escape(term_lower))
        if re.search(pattern, lowered):
            return True
    return False


def clean_quality_text(value):
    text = strip_html(value)
    # Some blogs append tag clouds, previous posts and subscription footers. Those
    # snippets can mention LLMs even when the current article is not about AI.
    for marker in (
        "This is a link post by",
        "Sponsor me",
        "Tags:",
        "Notes on the",
        "Related posts",
        "Previous post",
        "Next post",
    ):
        index = text.find(marker)
        if index >= 0:
            text = text[:index]
    return text.strip()


def strong_ai_hits(text):
    return matched_signals(text, STRONG_AI_SIGNALS, limit=6)


def matched_signals(text, signals, limit=4):
    lowered = text.lower()
    hits = []
    for signal in signals:
        if signal.lower() in lowered:
            hits.append(signal)
    return hits[:limit]


def display_signal(signal):
    return ZH_TERMS.get(signal.lower(), signal)


def build_quality_review(title, summary, body, tags, category, grade, quality_type, quality_score, low_hits, title_low_hit, ai_hits):
    text = " ".join([title or "", summary or "", clean_quality_text(body)])
    positives = matched_signals(text, DEPTH_SIGNALS + OFFICIAL_ALLOWED_SIGNALS + AI_CONTEXT_TERMS)
    reasons = []
    penalties = []

    if category == PRACTICE_CATEGORY:
        reasons.append("实战方法优先：匹配 Agent / Prompt / Vibe Coding 工作流方向")
    elif category == CREATOR_CATEGORY:
        reasons.append("核心博主观点：仅保留 AI/LLM/Agent/Prompt/Coding 相关内容")
    elif category == CORE_CATEGORY:
        reasons.append("官方动态：仅保留模型、产品能力、API 或企业应用相关")
    elif category == SOLO_CATEGORY:
        reasons.append("独立开发者案例：关注 AI 产品方法论与分发实践")

    if positives:
        reasons.append("命中高价值信号：" + " / ".join(display_signal(hit) for hit in positives[:4]))
    if ai_hits:
        reasons.append("主体明确相关：" + " / ".join(display_signal(hit) for hit in ai_hits[:3]))
    if grade == "A":
        reasons.append("一手/核心来源加权")
    if quality_score >= TOP_QUALITY_SCORE:
        reasons.append("可进入 Top/日报候选")
    elif quality_score >= DEFAULT_QUALITY_SCORE:
        reasons.append("默认信息流保留")
    else:
        reasons.append("低于默认阈值，仅进入归档")

    if low_hits:
        penalties.append("包含普通通知/弱价值信号")
    if title_low_hit:
        penalties.append("标题疑似低价值或噪音")
    if category in (CREATOR_CATEGORY, PRACTICE_CATEGORY, SOLO_CATEGORY) and not ai_hits:
        penalties.append("主体缺少明确 AI/LLM/Agent/Prompt/Coding 语境")
    if category == CORE_CATEGORY and not any(hit in text.lower() for hit in OFFICIAL_ALLOWED_SIGNALS):
        penalties.append("官方内容缺少模型/API/产品能力/企业应用信号")

    return {
        "score": quality_score,
        "tier": "top" if quality_score >= TOP_QUALITY_SCORE else ("default" if quality_score >= DEFAULT_QUALITY_SCORE else "archive"),
        "isDefaultVisible": quality_score >= DEFAULT_QUALITY_SCORE,
        "isTopEligible": quality_score >= TOP_QUALITY_SCORE,
        "reasons": reasons[:4],
        "penalties": penalties[:3],
        "reviewer": "content-experience-v1",
    }


def quality_sort_key(item):
    tier_rank = {"top": 2, "default": 1, "archive": 0}
    review = item.get("qualityReview", {})
    return (
        tier_rank.get(review.get("tier"), 0),
        item.get("qualityScore", 0),
        item.get("readingScore", 0),
        item.get("sourceGrade") == "A",
        item.get("importance", 0),
    )


def quality_profile(title, summary, body, tags, category, grade):
    quality_body = clean_quality_text(body)
    text = " ".join([title or "", summary or "", quality_body])
    title_text = (title or "").lower()
    signal_counts = {name: count_signals(text, signals) for name, signals in QUALITY_SIGNALS.items()}
    best_type = max(signal_counts, key=signal_counts.get)
    positive_hits = sum(signal_counts.values())
    ai_hits = strong_ai_hits(text)
    low_hits = count_signals(text, LOW_VALUE_SIGNALS)
    title_low_hit = any(signal in title_text for signal in LOW_VALUE_TITLE_SIGNALS)

    score = positive_hits * 18 - low_hits * 18
    if category == PRACTICE_CATEGORY:
        score += 24
    if category == CREATOR_CATEGORY and best_type in ("technical_update", "application_method"):
        score += 16
    if category == SOLO_CATEGORY:
        score += 34
        if positive_hits == 0:
            best_type = "application_method"
    if grade == "A":
        score += 8
    if len(strip_html(body)) > 700:
        score += 8
    if matched_signals(text, DEPTH_SIGNALS):
        score += 12
    if category in (CREATOR_CATEGORY, PRACTICE_CATEGORY, SOLO_CATEGORY) and not ai_hits:
        score -= 75
        if positive_hits < 2:
            best_type = "general"
    if category == CORE_CATEGORY and not matched_signals(text, OFFICIAL_ALLOWED_SIGNALS):
        score -= 55
        if positive_hits < 2:
            best_type = "general"
    if title_low_hit:
        score -= 45
    if positive_hits == 0:
        best_type = "general"
    quality_score = max(0, min(score, 100))
    return {
        "qualityScore": quality_score,
        "qualityType": best_type,
        "qualityLabelZh": QUALITY_LABELS_ZH.get(best_type, QUALITY_LABELS_ZH["general"]),
        "qualitySignals": signal_counts,
        "lowValueSignals": low_hits,
        "titleLowValue": title_low_hit,
        "qualityReview": build_quality_review(title, summary, body, tags, category, grade, best_type, quality_score, low_hits, title_low_hit, ai_hits),
    }


def summarize_text(title, body, source_name):
    text = strip_html(body)
    if not text:
        return "{} from {}. Included for AI tracking; open the original article to verify details.".format(title, source_name)
    sentences = re.split(r"(?<=[.!?\u3002\uff01\uff1f])\s+", text)
    useful = [s.strip() for s in sentences if len(s.strip()) > 40]
    summary = " ".join(useful[:2]) or text[:260]
    if len(summary) < 80:
        summary = "{} from {}. Useful for deciding whether the original article deserves a deeper read.".format(title, source_name)
    return summary[:420]


def pick_sentence(text, keywords, fallback):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?\u3002\uff01\uff1f])\s+", strip_html(text)) if len(s.strip()) > 30]
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            return localize_text(sentence[:220])
    if sentences:
        return localize_text(sentences[0][:220])
    return fallback


def intelligence_brief(title, summary, body, source_name, tags, category, quality_type, related_count=1):
    text = " ".join([title or "", summary or "", body or ""])
    tag_text = "\u3001".join(readable_tags(tags)[:3]) or "AI"
    what = pick_sentence(
        text,
        ("launch", "release", "introduce", "announce", "add", "model", "api", "agent", "workflow", "benchmark"),
        "\u8fd9\u6761\u60c5\u62a5\u6765\u81ea{}\uff0c\u4e3b\u8981\u805a\u7126{}\u76f8\u5173\u7684\u6280\u672f\u3001\u4ea7\u54c1\u6216\u5e94\u7528\u52a8\u6001\u3002".format(source_name, tag_text),
    )
    why = pick_sentence(
        text,
        ("enterprise", "developer", "production", "workflow", "cost", "latency", "quality", "agent", "reasoning", "coding"),
        "\u5b83\u503c\u5f97\u5173\u6ce8\uff0c\u56e0\u4e3a\u8fd9\u7c7b\u52a8\u6001\u53ef\u80fd\u5f71\u54cd AI \u4ea7\u54c1\u80fd\u529b\u3001\u4f01\u4e1a\u843d\u5730\u8282\u594f\u6216\u4e2a\u4eba\u5de5\u4f5c\u6d41\u6548\u7387\u3002",
    )
    if quality_type == "application_method" or category == PRACTICE_CATEGORY:
        takeaway = "\u5efa\u8bae\u5c06\u5b83\u5f53\u4f5c\u65b9\u6cd5\u8bba\u7d20\u6750\uff1a\u91cd\u70b9\u770b\u5176\u5de5\u4f5c\u6d41\u3001\u63d0\u793a\u8bcd\u3001Agent \u7f16\u6392\u6216\u843d\u5730\u6b65\u9aa4\u662f\u5426\u80fd\u590d\u7528\u3002"
    elif category == CORE_CATEGORY:
        takeaway = "\u5bf9\u4f01\u4e1a\u7528\u6237\uff0c\u5efa\u8bae\u5173\u6ce8\u5b83\u662f\u5426\u4f1a\u5e26\u6765\u65b0\u7684 API\u3001\u6a21\u578b\u80fd\u529b\u3001\u96c6\u6210\u65b9\u5f0f\u6216\u6210\u672c\u7ed3\u6784\u53d8\u5316\u3002"
    else:
        takeaway = "\u5bf9 AI \u7231\u597d\u8005\uff0c\u5efa\u8bae\u628a\u5b83\u653e\u5165\u672c\u5468\u8d8b\u52bf\u89c2\u5bdf\uff0c\u770b\u5b83\u662f\u5426\u4ee3\u8868\u65b0\u7684\u5de5\u5177\u7528\u6cd5\u6216\u6280\u672f\u65b9\u5411\u3002"
    if category == CORE_CATEGORY:
        audience = "\u4f01\u4e1a\u51b3\u7b56\u8005\u3001\u4ea7\u54c1\u7ecf\u7406\u3001AI \u5e94\u7528\u56e2\u961f"
    elif category == CREATOR_CATEGORY:
        audience = "AI \u7231\u597d\u8005\u3001\u7814\u53d1\u5de5\u7a0b\u5e08\u3001LLM \u5b9e\u8df5\u8005"
    elif category == SOLO_CATEGORY:
        audience = "\u72ec\u7acb\u5f00\u53d1\u8005\u3001AI \u521b\u4e1a\u8005\u3001\u4e2a\u4eba\u6548\u7387\u5de5\u4f5c\u8005"
    else:
        audience = "Prompt / Agent / Vibe Coding \u5b9e\u6218\u7528\u6237"
    reason_tail = "\u5df2\u5408\u5e76 {} \u4e2a\u76f8\u5173\u6765\u6e90".format(related_count) if related_count > 1 else "\u6765\u81ea\u6838\u5fc3\u8ffd\u8e2a\u6e90"
    return {
        "whatHappened": what,
        "whyItMatters": why,
        "takeaway": takeaway,
        "audience": audience,
        "recommendationReason": "\u4f18\u5148\u9605\u8bfb\uff1a{}\uff1b{}\u3002".format(QUALITY_LABELS_ZH.get(quality_type, "\u9ad8\u4ef7\u503c\u52a8\u6001"), reason_tail),
    }


def localize_text(text):
    result = text or ""
    phrase_map = {
        "Focus:": "\u5173\u6ce8\u65b9\u5411\uff1a",
        "Worth reading for practical context and source details.": "\u503c\u5f97\u9605\u8bfb\uff0c\u53ef\u5e2e\u52a9\u7406\u89e3\u5b9e\u6218\u80cc\u666f\u4e0e\u4fe1\u606f\u6765\u6e90\u3002",
        "Open the original article for full evidence and nuance.": "\u5efa\u8bae\u6253\u5f00\u539f\u6587\u67e5\u770b\u5b8c\u6574\u8bc1\u636e\u548c\u7ec6\u8282\u3002",
        "Included for AI tracking; open the original article to verify details.": "\u5df2\u7eb3\u5165 AI \u60c5\u62a5\u8ddf\u8e2a\uff0c\u5efa\u8bae\u6253\u5f00\u539f\u6587\u6838\u9a8c\u7ec6\u8282\u3002",
        "Useful for deciding whether the original article deserves a deeper read.": "\u9002\u5408\u7528\u4e8e\u5feb\u901f\u5224\u65ad\u8fd9\u7bc7\u5185\u5bb9\u662f\u5426\u503c\u5f97\u6df1\u8bfb\u3002",
        "from": "\u6765\u81ea", "for": "\u9762\u5411", "with": "\u7ed3\u5408", "and": "\u4ee5\u53ca",
    }
    for en, zh in phrase_map.items():
        result = re.sub(r"\b{}\b".format(re.escape(en)), zh, result, flags=re.IGNORECASE)
    for en, zh in sorted(ZH_TERMS.items(), key=lambda item: len(item[0]), reverse=True):
        result = re.sub(r"\b{}\b".format(re.escape(en)), zh, result, flags=re.IGNORECASE)
    return result


def readable_tags(tags):
    return [ZH_TERMS.get(str(tag).lower(), str(tag)) for tag in tags[:4]]


def chinese_headline(title, source_name, tags):
    if re.search(r"[\u4e00-\u9fff]", title):
        return title
    localized = localize_text(title)
    return "\u3010{}\u3011{}".format(source_name, localized)


def chinese_summary(source_name, summary, tags):
    tag_text = "\u3001".join(readable_tags(tags)) or "AI"
    localized = localize_text(summary[:220])
    if len(re.findall(r"[\u4e00-\u9fff]", localized)) < 12:
        localized = "\u7cfb\u7edf\u5df2\u4ece\u6807\u9898\u3001\u6458\u8981\u548c\u53ef\u6293\u53d6\u6b63\u6587\u4e2d\u8bc6\u522b\u51fa\u4e3b\u9898\uff0c\u5e76\u7eb3\u5165 2026 \u5e74\u81f3\u4eca AI \u60c5\u62a5\u6d41\u3002"
    return "\u6765\u6e90\uff1a{}\u3002\u4e3b\u9898\uff1a{}\u3002{}\u5efa\u8bae\u5173\u6ce8\u5b83\u5bf9\u4ea7\u54c1\u3001\u4f01\u4e1a\u843d\u5730\u6216\u4e2a\u4eba\u5de5\u4f5c\u6d41\u7684\u542f\u53d1\u3002".format(source_name, tag_text, localized)


def key_points_from_text(body, tags):
    text = strip_html(body)
    candidates = []
    for sentence in re.split(r"(?<=[.!?\u3002\uff01\uff1f])\s+", text):
        s = sentence.strip()
        lowered = s.lower()
        if 35 <= len(s) <= 180 and any(k in lowered for k in ("ai", "agent", "model", "enterprise", "llm", "open-source", "prompt", "coding")):
            candidates.append(s)
    if not candidates:
        tag_text = ", ".join(tags[:3])
        candidates = ["Focus: {}".format(tag_text or "AI"), "Worth reading for practical context and source details.", "Open the original article for full evidence and nuance."]
    return candidates[:3]


def chinese_points(points, tags):
    result = []
    defaults = [
        "\u4fe1\u606f\u6765\u6e90\u5df2\u7eb3\u5165\u6838\u5fc3\u8ffd\u8e2a\u6e05\u5355\uff0c\u9002\u5408\u4f5c\u4e3a\u8fd1\u671f AI \u52a8\u6001\u89c2\u5bdf\u3002",
        "\u53ef\u4f18\u5148\u5173\u6ce8\u5176\u5bf9\u4f01\u4e1a\u5e94\u7528\u3001Agent \u5de5\u4f5c\u6d41\u6216\u5b9e\u6218\u65b9\u6cd5\u7684\u542f\u53d1\u3002",
        "\u82e5\u8981\u505a\u51b3\u7b56\u6216\u6df1\u5ea6\u5b66\u4e60\uff0c\u5efa\u8bae\u70b9\u51fb\u539f\u6587\u6838\u9a8c\u5b8c\u6574\u8bed\u5883\u3002",
    ]
    for index, point in enumerate(points[:3]):
        text = localize_text(point)
        if not re.search(r"[\u4e00-\u9fff]", text):
            text = defaults[index]
        result.append(text[:180])
    return result


def reading_score(grade, importance, category, body, quality_score):
    score = importance * 12
    if grade == "A":
        score += 20
    if category in (CREATOR_CATEGORY, PRACTICE_CATEGORY, SOLO_CATEGORY):
        score += 15
    if len(strip_html(body)) > 600:
        score += 10
    score += int(quality_score * 0.35)
    return min(score, 100)


def apply_intelligence_fields(item):
    body = item.get("bodyText") or item.get("rawBody", "")
    summary = summarize_text(item["title"], body, item["sourceName"])
    points = key_points_from_text(body, item.get("tags", []))
    quality = quality_profile(item["title"], summary, body, item.get("tags", []), item["category"], item["sourceGrade"])
    item.update(quality)
    item["summary"] = summary
    item["summaryZh"] = chinese_summary(item["sourceName"], summary, item.get("tags", []))
    item["keyPoints"] = points
    item["keyPointsZh"] = chinese_points(points, item.get("tags", []))
    item["readingScore"] = reading_score(item["sourceGrade"], item["importance"], item["category"], body, item["qualityScore"])
    item["intelligenceBrief"] = intelligence_brief(
        item["title"],
        summary,
        body,
        item["sourceName"],
        item.get("tags", []),
        item["category"],
        item["qualityType"],
        len(item.get("relatedSources", [])) or 1,
    )
    return item


def make_item(title, date, source_name, link, grade, category, tags, importance, body="", image_url="", publisher=""):
    clean_body = strip_html(body)[:5200]
    item = {
        "title": title,
        "titleZh": chinese_headline(title, source_name, tags),
        "summary": "",
        "summaryZh": "",
        "keyPoints": [],
        "keyPointsZh": [],
        "imageUrl": image_url,
        "date": date,
        "sourceName": source_name,
        "publisher": publisher,
        "sourceUrl": link,
        "sourceGrade": grade,
        "category": category,
        "contentType": "article" if category in (CREATOR_CATEGORY, SOLO_CATEGORY) else "news",
        "readingScore": 0,
        "tags": tags,
        "importance": importance,
        "rawBody": clean_body,
        "bodyText": clean_body,
        "contentFetched": False,
        "relatedSources": [{"sourceName": source_name, "sourceUrl": link, "sourceGrade": grade, "publisher": publisher}],
        "sourceCount": 1,
        "aggregatedEvent": False,
    }
    return apply_intelligence_fields(item)


def keep_item(item):
    return bool(
        item["title"]
        and item["sourceUrl"]
        and is_in_scope(item["date"])
        and is_relevant(item["title"])
        and item.get("qualityScore", 0) >= MIN_QUALITY_SCORE
        and item.get("qualityType") != "general"
        and not item.get("titleLowValue")
    )


def parse_feed_items(feed_text, source_name, category, grade, tags, importance, limit):
    root = ET.fromstring(feed_text)
    items = []
    rss_items = root.findall("./channel/item")
    if rss_items:
        for node in rss_items[:limit]:
            title = clean_title(node.findtext("title"))
            date = normalize_date(node.findtext("pubDate") or node.findtext("dc:date") or "")
            link = node.findtext("link") or ""
            body = node.findtext("description") or node.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
            image = extract_image(body)
            enclosure = node.find("enclosure")
            if not image and enclosure is not None and enclosure.attrib.get("type", "").startswith("image/"):
                image = enclosure.attrib.get("url", "")
            items.append(make_item(title, date, source_name, link, grade, category, tags, importance, body, image))
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for node in root.findall("atom:entry", ns)[:limit]:
        link_node = node.find("atom:link", ns)
        link = link_node.attrib.get("href", "") if link_node is not None else ""
        title = clean_title(node.findtext("atom:title", default="", namespaces=ns))
        date = normalize_date(node.findtext("atom:updated", default="", namespaces=ns) or node.findtext("atom:published", default="", namespaces=ns))
        body = node.findtext("atom:summary", default="", namespaces=ns) or node.findtext("atom:content", default="", namespaces=ns) or ""
        items.append(make_item(title, date, source_name, link, grade, category, tags, importance, body, extract_image(body)))
    return items


def parse_google_news(feed_text, tracked_source, category, tags, importance, limit):
    root = ET.fromstring(feed_text)
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for node in channel.findall("item")[:limit]:
        title = clean_title(node.findtext("title"))
        date = normalize_date(node.findtext("pubDate") or "")
        link = node.findtext("link") or ""
        source_node = node.find("source")
        publisher = source_node.text.strip() if source_node is not None and source_node.text else "Google News"
        description = node.findtext("description") or ""
        items.append(make_item(title, date, tracked_source, link, "B", category, tags, importance, description, extract_image(description), publisher))
    return items


def collect_rss():
    items = []
    coverage = {
        source["name"]: {"rss": source["url"], "rssItems": 0, "googleItems": 0, "status": "pending"}
        for source in RSS_SOURCES
    }

    def collect_one(source):
        try:
            parsed = parse_feed_items(fetch_text(source["url"], timeout=8), source["name"], source["category"], "A", source["tags"], source["importance"], limit=40)
            parsed = [item for item in parsed if keep_item(item)]
            return source, parsed, None
        except Exception as exc:
            return source, [], exc

    with ThreadPoolExecutor(max_workers=RSS_WORKERS) as executor:
        futures = [executor.submit(collect_one, source) for source in RSS_SOURCES]
        for future in as_completed(futures):
            source, parsed, exc = future.result()
            if exc:
                coverage[source["name"]]["status"] = "failed: {}".format(exc)
                print("RSS source failed: {} ({})".format(source["name"], exc))
                continue
            coverage[source["name"]]["rssItems"] = len(parsed)
            coverage[source["name"]]["status"] = "ok"
            items.extend(parsed)
    return items, coverage


def source_query(name, category):
    if category == CORE_CATEGORY:
        return '"{}" AI model agent enterprise API release feature update'.format(name)
    if category == CREATOR_CATEGORY:
        return '"{}" AI LLM agent prompt coding workflow guide'.format(name)
    return '"{}" AI startup indie maker solo builder product workflow case study'.format(name)


def collect_google_news(source_pool, coverage):
    items = []
    query_specs = []
    for category, names in source_pool.items():
        for name in names:
            tags = [name, "enterprise" if category == CORE_CATEGORY else "creator"]
            importance = 5 if category != SOLO_CATEGORY else 4
            query_specs.append((name, source_query(name, category), category, tags, importance))
    query_specs.extend(EXTRA_QUERIES)

    seen_specs = set()
    unique_specs = []
    for name, query, category, tags, importance in query_specs:
        key = (name, query)
        if key in seen_specs:
            continue
        seen_specs.add(key)
        coverage.setdefault(name, {"rss": "", "rssItems": 0, "googleItems": 0, "status": "pending"})
        unique_specs.append((name, query, category, tags, importance))

    def collect_one(spec):
        name, query, category, tags, importance = spec
        try:
            parsed = parse_google_news(fetch_text(google_news_rss(query), timeout=6), name, category, tags, importance, limit=6)
            parsed = [item for item in parsed if keep_item(item)]
            return name, parsed, None
        except Exception as exc:
            return name, [], exc

    with ThreadPoolExecutor(max_workers=GOOGLE_WORKERS) as executor:
        futures = [executor.submit(collect_one, spec) for spec in unique_specs]
        for future in as_completed(futures):
            name, parsed, exc = future.result()
            if exc:
                if coverage[name].get("status") in ("pending", ""):
                    coverage[name]["status"] = "failed: {}".format(exc)
                print("Google News query failed: {} ({})".format(name, exc))
                continue
            coverage[name]["googleItems"] = coverage[name].get("googleItems", 0) + len(parsed)
            if coverage[name].get("status") in ("pending", ""):
                coverage[name]["status"] = "ok" if parsed else "no_high_value_items"
            items.extend(parsed)
    return items


def collect_curated_solo_items(coverage):
    items = []
    for spec in CURATED_SOLO_ITEMS:
        name = spec["sourceName"]
        coverage.setdefault(name, {"rss": "", "rssItems": 0, "googleItems": 0, "curatedItems": 0, "status": "pending"})
        item = make_item(
            spec["title"],
            spec["date"],
            name,
            spec["sourceUrl"],
            "B",
            SOLO_CATEGORY,
            spec["tags"],
            5,
            spec["body"],
            "",
            spec["publisher"],
        )
        if keep_item(item):
            coverage[name]["curatedItems"] = coverage[name].get("curatedItems", 0) + 1
            if coverage[name].get("status") in ("pending", "no_high_value_items", ""):
                coverage[name]["status"] = "ok_curated"
            items.append(item)
    return items


def event_key(item):
    title = item.get("title", "").lower()
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    for source in (item.get("sourceName", ""), item.get("publisher", "")):
        if source:
            title = title.replace(source.lower(), " ")
    title = re.sub(r"\b(ai|llm|the|a|an|and|or|to|for|with|on|in|of|by)\b", " ", title)
    title = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", title).strip()
    compact = re.sub(r"\s+", " ", title)
    if len(compact) < 18:
        compact = "{} {}".format(item.get("sourceName", "").lower(), compact)
    return compact[:120]


def enrich_article_bodies(items):
    prioritized = sorted(items, key=lambda item: (item.get("date", ""), item.get("readingScore", 0), item.get("importance", 0)), reverse=True)
    fetched = 0
    candidates = [item for item in prioritized if item.get("sourceUrl", "").startswith("http")][: ARTICLE_FETCH_LIMIT * 3]

    def fetch_article(item):
        try:
            return item, extract_article_text(fetch_text(item["sourceUrl"], timeout=6))
        except Exception:
            return item, ""

    with ThreadPoolExecutor(max_workers=ARTICLE_WORKERS) as executor:
        futures = [executor.submit(fetch_article, item) for item in candidates]
        for future in as_completed(futures):
            if fetched >= ARTICLE_FETCH_LIMIT:
                break
            item, article_text = future.result()
            if len(article_text) > max(400, len(item.get("bodyText", ""))):
                item["bodyText"] = article_text
                item["contentFetched"] = True
                apply_intelligence_fields(item)
                fetched += 1
    return fetched


def dedupe(items):
    groups = {}
    for item in items:
        groups.setdefault((item.get("date"), event_key(item)), []).append(item)

    result = []
    for (_, key), group in groups.items():
        group.sort(key=lambda x: (x["sourceGrade"] == "A", x["qualityScore"], x["readingScore"], x["importance"]), reverse=True)
        primary = group[0]
        related = []
        seen_urls = set()
        for candidate in group:
            for source in candidate.get("relatedSources", []):
                url = source.get("sourceUrl", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    related.append(source)
        primary["eventId"] = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[:80] or str(len(result) + 1)
        primary["relatedSources"] = related or primary.get("relatedSources", [])
        primary["sourceCount"] = len(primary["relatedSources"])
        primary["aggregatedEvent"] = len(group) > 1 or primary["sourceCount"] > 1
        primary["readingScore"] = min(100, primary.get("readingScore", 0) + min(12, (primary["sourceCount"] - 1) * 4))
        apply_intelligence_fields(primary)
        result.append(primary)
    return result


def source_health(coverage):
    total = len(coverage)
    ok = sum(1 for value in coverage.values() if str(value.get("status", "")).startswith("ok"))
    empty = sum(1 for value in coverage.values() if str(value.get("status", "")).startswith("no_high_value_items"))
    failed = total - ok - empty
    fallback = sum(1 for value in coverage.values() if value.get("googleItems", 0) and not value.get("rssItems", 0))
    curated = sum(1 for value in coverage.values() if value.get("curatedItems", 0))
    return {"total": total, "ok": ok, "empty": empty, "failed": failed, "fallback": fallback, "curated": curated}


def source_health_details(coverage, source_pool):
    categories = {}
    for category, names in source_pool.items():
        for name in names:
            categories[name] = category
    for source in RSS_SOURCES:
        categories[source["name"]] = source["category"]
    rows = []
    for name, value in sorted(coverage.items(), key=lambda item: (categories.get(item[0], ""), item[0].lower())):
        status = str(value.get("status", "pending"))
        if status.startswith("ok"):
            label = "正常"
        elif status.startswith("no_high_value_items"):
            label = "暂无高价值内容"
        else:
            label = "失败"
        rows.append({
            "name": name,
            "category": categories.get(name, PRACTICE_CATEGORY if name in {q[0] for q in EXTRA_QUERIES} else ""),
            "status": status,
            "statusLabelZh": label,
            "rssItems": value.get("rssItems", 0),
            "googleItems": value.get("googleItems", 0),
            "curatedItems": value.get("curatedItems", 0),
            "totalItems": value.get("rssItems", 0) + value.get("googleItems", 0) + value.get("curatedItems", 0),
            "rss": value.get("rss", ""),
        })
    return rows


def top_stories(items, limit=10, max_per_source=2):
    ranked = sorted(
        [item for item in items if item.get("qualityReview", {}).get("isTopEligible")],
        key=quality_sort_key,
        reverse=True,
    )
    top = []
    source_counts = {}
    seen_events = set()
    for item in ranked:
        event_id = item.get("eventId") or item.get("title")
        source = item.get("sourceName", "")
        if event_id in seen_events:
            continue
        if source_counts.get(source, 0) >= max_per_source:
            continue
        top.append(item)
        seen_events.add(event_id)
        source_counts[source] = source_counts.get(source, 0) + 1
        if len(top) >= limit:
            break
    for index, item in enumerate(top, start=1):
        item["topRank"] = index
        item["isTopStory"] = True
    return top


def latest_item_date(items):
    dates = sorted(item.get("date", "") for item in items if item.get("date"))
    return dates[-1] if dates else datetime.now(timezone.utc).strftime("%Y-%m-%d")


def recent_items(items, days=7):
    end = datetime.strptime(latest_item_date(items), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    start = start.fromtimestamp(start.timestamp() - (days - 1) * 86400, tz=timezone.utc)
    result = []
    for item in items:
        try:
            date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if start <= date <= end:
            result.append(item)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), result


def top_counts(pairs, limit=8):
    ranked = sorted(pairs.items(), key=lambda pair: (-pair[1], pair[0].lower()))
    return [{"name": name, "count": count} for name, count in ranked[:limit] if count > 0]


def build_trends(items, source_pool):
    start, end, scoped = recent_items(items, days=7)
    company_names = set(source_pool.get(CORE_CATEGORY, [])) | {source["name"] for source in RSS_SOURCES if source["category"] == CORE_CATEGORY}
    company_counts = {}
    model_counts = {}
    topic_counts = {}
    quality_counts = {}

    for item in scoped:
        text = " ".join([
            item.get("title", ""),
            item.get("titleZh", ""),
            item.get("summary", ""),
            item.get("summaryZh", ""),
            " ".join(str(tag) for tag in item.get("tags", [])),
            item.get("sourceName", ""),
        ]).lower()
        if item.get("sourceName") in company_names:
            company_counts[item["sourceName"]] = company_counts.get(item["sourceName"], 0) + 1
        for company in company_names:
            if company.lower() in text:
                company_counts[company] = company_counts.get(company, 0) + 1
        for model in TREND_MODEL_TERMS:
            if model.lower() in text:
                model_counts[model] = model_counts.get(model, 0) + 1
        for topic, signals in TREND_TOPIC_TERMS.items():
            if any(signal.lower() in text for signal in signals):
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        label = item.get("qualityLabelZh") or item.get("qualityType") or "未分类"
        quality_counts[label] = quality_counts.get(label, 0) + 1

    return {
        "windowDays": 7,
        "startDate": start,
        "endDate": end,
        "itemCount": len(scoped),
        "companies": top_counts(company_counts),
        "models": top_counts(model_counts),
        "topics": top_counts(topic_counts),
        "qualityTypes": top_counts(quality_counts, limit=4),
    }


def digest_line_item(item, index):
    brief = item.get("intelligenceBrief", {})
    title = item.get("titleZh") or item.get("title")
    url = item.get("sourceUrl", "")
    link = "[{}]({})".format(title, url) if url else title
    return "\n{}. {}\n   - 推荐理由：{}\n   - 启发：{}\n   - 来源：{} / {} / {}".format(
        index,
        link,
        strip_html(brief.get("recommendationReason") or item.get("summaryZh") or item.get("summary")),
        strip_html(brief.get("takeaway") or item.get("summaryZh") or item.get("summary")),
        item.get("sourceName", ""),
        item.get("date", ""),
        item.get("qualityLabelZh", ""),
    )


def default_visible_items(items):
    return [item for item in items if item.get("qualityReview", {}).get("isDefaultVisible")]


def archive_items(items):
    return [item for item in items if not item.get("qualityReview", {}).get("isDefaultVisible")]


def write_daily_digest(payload):
    items = payload.get("items", [])
    top = (payload.get("topStories") or items[:10])[:10]
    trends = payload.get("trends", {})
    health = payload.get("sourceHealth", {})
    date = latest_item_date(items)
    methods = [item for item in items if item.get("qualityType") == "application_method" or item.get("category") == PRACTICE_CATEGORY][:5]
    a_grade = [item for item in items if item.get("sourceGrade") == "A"][:5]

    trend_lines = []
    for section, title in (("companies", "公司热度"), ("models", "模型热度"), ("topics", "主题热度")):
        values = trends.get(section, [])
        trend_lines.append("### {}".format(title))
        trend_lines.extend("- {}：{} 条".format(row["name"], row["count"]) for row in values[:6])
        if not values:
            trend_lines.append("- 暂无明显集中趋势")
        trend_lines.append("")

    lines = [
        "# AI Daily Radar 日报 - {}".format(date),
        "",
        "> 今日默认展示 {} 条高质量情报，Top {} 已精选。来源健康：{}/{} 正常，{} 暂无高价值内容，{} 精选兜底，{} 失败。".format(
            len(items),
            len(top),
            health.get("ok", 0),
            health.get("total", 0),
            health.get("empty", 0),
            health.get("curated", 0),
            health.get("failed", 0),
        ),
        "",
        "## 今日必看 Top {}".format(len(top)),
    ]
    lines.extend(digest_line_item(item, index) for index, item in enumerate(top, start=1))
    lines.extend(["", "## 7 天趋势雷达", ""])
    lines.extend(trend_lines)
    lines.extend(["## 方法论与实战"])
    lines.extend("- [{}]({})：{}".format(item.get("titleZh") or item.get("title"), item.get("sourceUrl"), strip_html(item.get("intelligenceBrief", {}).get("takeaway") or item.get("summaryZh") or item.get("summary"))) for item in methods)
    lines.extend(["", "## A级/一手来源观察"])
    lines.extend("- [{}]({})：{}".format(item.get("titleZh") or item.get("title"), item.get("sourceUrl"), item.get("sourceName", "")) for item in a_grade)
    lines.extend([
        "",
        "## 阅读建议",
        "- 先读 Top 10，快速判断今天最值得跟进的模型、产品和方法论变化。",
        "- 对企业应用相关内容，重点看 API、Agent 工作流、成本结构和落地路径。",
        "- 如果感兴趣请点击查看原文章，做决策前建议核验完整语境。",
        "",
    ])

    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    digest_path = DIGEST_DIR / "{}.md".format(date)
    latest_path = DIGEST_DIR / "latest.md"
    markdown = "\n".join(lines)
    digest_path.write_text(markdown, encoding="utf-8")
    latest_path.write_text(markdown, encoding="utf-8")
    index_path = DIGEST_DIR / "index.json"
    archive_index = {
        "latest": "data/digests/latest.md",
        "digests": [{
            "date": date,
            "path": "data/digests/{}.md".format(date),
            "itemCount": len(items),
            "topStoryCount": len(top),
            "generatedAt": payload.get("updatedAt"),
        }],
    }
    index_path.write_text(json.dumps(archive_index, ensure_ascii=True, indent=2), encoding="utf-8")
    return archive_index["digests"][0] | {"latestPath": archive_index["latest"]}


def main():
    source_pool = load_source_pool()
    items, coverage = collect_rss()
    items.extend(collect_google_news(source_pool, coverage))
    items.extend(collect_curated_solo_items(coverage))
    fetched_articles = enrich_article_bodies(items)
    items = dedupe(items)
    items.sort(key=lambda x: (x["date"], quality_sort_key(x)), reverse=True)
    items = items[:MAX_ITEMS]
    default_items = default_visible_items(items)
    archive = archive_items(items)
    top = top_stories(default_items)

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "yearStart": YEAR_START,
        "coverageWindow": "YTD",
        "qualityPolicy": {
            "minQualityScore": MIN_QUALITY_SCORE,
            "defaultQualityScore": DEFAULT_QUALITY_SCORE,
            "topQualityScore": TOP_QUALITY_SCORE,
            "defaultMode": "high_quality",
            "topPolicy": "Top and digest only use qualityScore >= 80. Top may contain fewer than 10 items.",
            "preferredTypes": QUALITY_LABELS_ZH,
            "blockedLowValueSignals": LOW_VALUE_SIGNALS,
        },
        "policy": {
            "A": "Official RSS, official blog, or first-party source.",
            "B": "Google News query for a tracked source or reputable media/newsletter source.",
            "C": "Secondary commentary; not included in the default daily feed yet.",
        },
        "p0Quality": {
            "articleFetchLimit": ARTICLE_FETCH_LIMIT,
            "fetchedArticles": fetched_articles,
            "dedupeStrategy": "same-date normalized event title; related sources are merged into one event card",
            "topStoryCount": len(top),
            "defaultVisibleCount": len(default_items),
            "archiveCount": len(archive),
        },
        "sourceHealth": source_health(coverage),
        "sourceHealthDetails": source_health_details(coverage, source_pool),
        "sourceCoverage": coverage,
        "trends": build_trends(items, source_pool),
        "topStories": top,
        "items": default_items,
        "archiveItems": archive,
        "allItemsCount": len(items),
    }
    payload["digestArchive"] = write_daily_digest(payload)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print("Updated {} with {} items from {} tracked sources.".format(OUT_FILE, len(payload["items"]), len(coverage)))


if __name__ == "__main__":
    main()
