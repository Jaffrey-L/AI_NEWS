# Static site deployment

The public site is served from `main` by GitHub Pages at <https://jaffrey-l.github.io/AI_NEWS/>. No model API, paid feed, cron job, database, or server process is required to read the checked-in weekly editions and Amazon articles.

## Refresh the checked-in data

Run these commands locally before committing a new snapshot:

```bash
python3 scripts/update_ai_news.py
python3 scripts/validate_news_data.py
python3 scripts/update_amazon_news.py
python3 scripts/validate_amazon_news.py
python3 scripts/build_site_payload.py
```

`update_ai_news.py` writes the news snapshot and dated daily digest. `update_amazon_news.py` reads public publisher pages and official Amazon feeds; it keeps the previous Amazon snapshot if a source fails. `build_site_payload.py` combines the checked-in weekly editions, reviewed card excerpts, source registry, and Amazon snapshot for the static frontend. A new weekly edition without reviewed cards uses linked excerpts for its news card and leaves unsupported cards empty.

The model-based weekly publisher is optional and may incur provider charges. It is not part of this zero-cost deployment or any scheduled job.

## Check the page

```bash
python3 -m http.server 8000
```

In another terminal:

```bash
npm install
npx playwright install chromium
SITE_URL=http://127.0.0.1:8000 npm run validate:frontend
```

The public deployment follows an approved merge to `main`. Check the GitHub Pages build status, then open the public URL and verify the current weekly interpretation, its original links, the Amazon week label, source archive, and mobile layout. A successful merge alone does not prove that Pages has published the new commit.

## Optional Linux mirror

If a separate Linux mirror is needed, serve the repository as static files from the directory containing `index.html`. The page loads `workspace.css`, `app.js`, and `data/site-payload.js` with relative paths. Keep these files together. A static Nginx root with `try_files $uri $uri/ =404` is sufficient; the frontend does not need a Python or Node process in production.
