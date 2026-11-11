# AI 周读

The homepage shows a source-linked weekly AI interpretation, starting from the most recent completed week. Readers can select earlier weeks and open original publications. The Amazon tab shows dated, linked articles from the requested publishers' public websites and three official Amazon RSS feeds. The AI 承接 tab lists source status and the full Amazon article archive. Public website articles are not represented as WeChat posts.

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

The AI collector polls 16 company and creator RSS/Atom feeds. `sources.json` also lists a broader query pool; a name in that pool is not proof that its article has entered a published edition. The Amazon collector reads four public websites corresponding to the five requested account names (雨果网 and 雨果跨境 share one site), plus three official Amazon RSS feeds. It stores only dated titles, short metadata descriptions, and original links. WeChat originals are not collected. The paid X API is not used under the zero-cost requirement; Andrej Karpathy's public blog remains in the free RSS pool.

Refresh the free Amazon snapshot and rebuild the static reader:

```bash
python3 scripts/update_amazon_news.py
python3 scripts/validate_amazon_news.py
python3 scripts/build_site_payload.py
```

The Amazon page's three summary groups contain only articles dated within the current Monday–Sunday week; each article appears in at most one group. Older articles remain in the AI 承接 archive. The three groups show original titles and links, without generated descriptions. `data/editorial-cards.json` contains the reviewed excerpts for the existing nine AI weekly editions. A newly published week without reviewed cards uses cited paragraph excerpts for “大事” and leaves the other two groups empty until editorial review. Run `build_site_payload.py` after publishing a weekly edition. This is a manual static-site update; there is no paid or scheduled model run in the zero-cost deployment.

The model publisher below is a manual, optional tool. It is not scheduled or configured in the zero-cost deployment because provider API requests can incur charges. The existing weekly archive remains readable without a model API.

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
