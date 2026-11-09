# AI Daily Radar

AI Daily Radar is a static AI news dashboard with scheduled news collection.

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

## Frontend Validation

```bash
npm install
npx playwright install chromium
npm run validate:frontend
```

## Deployment

For Linux deployment, see:

[docs/deploy/linux-deploy.md](docs/deploy/linux-deploy.md)
