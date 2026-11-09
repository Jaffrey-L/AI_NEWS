# AI Daily Radar

AI Daily Radar leads with an automatically written AI opinion article. Each paragraph links to the source and shows a short, exact evidence excerpt. The original news dashboard remains below the article.

It tracks:

- Core AI company news
- AI builders and creators
- Solo/small-company AI builders
- Vibe Coding / Prompt / Agent practice

## Quick Start

```bash
python3 -m http.server 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Update News Data

```bash
python3 scripts/update_ai_news.py
python3 scripts/validate_news_data.py
```

## Publish an AI opinion article

Set `OPENAI_API_KEY` and `AI_NEWS_MODEL` in the server job environment, then run:

```bash
python3 scripts/generate_opinion.py
```

The job selects recent sources from `data/news.json`, asks the model for a Chinese opinion article, and checks every cited evidence excerpt against the selected source text. It publishes `data/opinion/latest.json` without an editorial approval step. If the model, sources, or citation checks fail, the prior article stays live and `data/opinion/status.json` reports the failed update. The model key is never sent to the browser. Source text is an excerpt, so this check confirms a quoted span and link, not that every interpretation is correct.

The publisher makes one model request per scheduled run, with a 120-second request timeout and a 5,000-output-token cap. Usage cost depends on the configured model and current provider pricing; watch the job log and provider usage before increasing frequency.

The article section shows a clear waiting state until the first successful run. Test the publisher without an API request using:

```bash
python3 -m unittest discover -s tests -p test_generate_opinion.py
```

The repository includes a one-time AI-authored seed article dated 2026-11-09 so the layout can be previewed before the scheduled model job is configured. Its `model` field is `assistant-seed`; it is not presented as an API run. The next successful scheduled run replaces it.

## Frontend Validation

```bash
npm install
npx playwright install chromium
npm run validate:frontend
```

## Deployment

For Linux deployment, see:

[docs/deploy/linux-deploy.md](docs/deploy/linux-deploy.md)
