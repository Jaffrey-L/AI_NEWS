# AI 周读

The homepage shows a source-linked weekly AI interpretation, starting from the most recent completed week. Readers can select earlier weeks and open original publications from links within each interpretation. The separate news dashboard is no longer shown.

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

## Publish weekly interpretations

Set `AI_NEWS_MODEL` and a provider key in the server job environment. The default provider is OpenAI (`OPENAI_API_KEY`). To use DeepSeek's Responses API, set `AI_NEWS_PROVIDER=deepseek`, `AI_NEWS_MODEL=deepseek-flash`, and `DEEPSEEK_API_KEY`. The endpoint is selected from a fixed allowlist; the key never chooses an arbitrary URL. Then run:

```bash
python3 scripts/generate_weekly.py
```

The job shortlists core company and creator sources from `data/news.json`, checks original publication dates against publisher feeds or pages, and groups them by completed ISO week. When a week has one verified non-OpenAI original, the dated OpenAI official feed may supplement that week. It publishes an edition only when two publishers can be cited. Missing weeks remain missing rather than receiving invented commentary. Existing editions remain untouched if a later model run fails. Each new edition is written to `data/weekly/YYYY-Www.json`; `data/weekly/index.json` drives the archive. The model key is never sent to the browser. A matching excerpt and link do not prove that every interpretation is correct.

The publisher makes one model request per unpublished eligible week, with a 120-second request timeout and a 5,000-output-token cap per request. Use `--max-weeks N` for a bounded historical backfill. Usage cost depends on the configured model and current provider pricing. DeepSeek's [Responses API documentation](https://api-docs.deepseek.com/guides/responses_api/) lists its compatible endpoint and models.

Test the publisher without an API request using:

```bash
python3 -m unittest discover -s tests -p 'test_generate_*.py'
```

The old single-article publisher remains for compatibility when no weekly edition exists. The site already contains source-checked weekly editions, so normal readers see the weekly archive first.

## Frontend Validation

```bash
npm install
npx playwright install chromium
npm run validate:frontend
```

## Deployment

For Linux deployment, see:

[docs/deploy/linux-deploy.md](docs/deploy/linux-deploy.md)
