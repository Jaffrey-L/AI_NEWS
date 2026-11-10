# Linux Deployment Guide

This guide deploys AI Daily Radar on a Linux server for testing or production.

The app is a static site. Python is only used to collect `data/news.json`.

Current collection scope:

- Default content window: current year to date, starting from `2026-01-01`
- Quality focus: technical updates, important feature updates, and AI application methods
- Recommended update cadence: every 12 hours, which satisfies daily update requirements with a morning/evening refresh rhythm

## 1. Server Requirements

Ubuntu/Debian example:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv nginx nodejs npm
```

Recommended:

- Python 3.10+
- Node.js 18+
- Nginx
- Git

## 2. Clone Repository

```bash
sudo mkdir -p /opt/ai-daily-radar
sudo chown -R "$USER":"$USER" /opt/ai-daily-radar
git clone https://github.com/Jaffrey-L/AI_NEWS.git /opt/ai-daily-radar
cd /opt/ai-daily-radar
```

## 3. Generate News Data

```bash
python3 scripts/update_ai_news.py
python3 scripts/validate_news_data.py
```

Expected validation output should look like:

```text
PASS news data validation: 200+ items, tracked sources covered, technical/feature/method items present.
```

The numbers may change over time, but validation should pass.

## 4. Quick Test Without Nginx

```bash
cd /opt/ai-daily-radar
python3 -m http.server 8000
```

Open:

```text
http://SERVER_IP:8000
```

If your server firewall is enabled:

```bash
sudo ufw allow 8000/tcp
```

## 5. Deploy With Nginx

Create an Nginx site:

```bash
sudo tee /etc/nginx/sites-available/ai-daily-radar >/dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    root /opt/ai-daily-radar;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /data/ {
        add_header Cache-Control "no-store";
        try_files $uri =404;
    }
}
EOF
```

Enable it:

```bash
sudo ln -sf /etc/nginx/sites-available/ai-daily-radar /etc/nginx/sites-enabled/ai-daily-radar
sudo nginx -t
sudo systemctl reload nginx
```

Open:

```text
http://SERVER_IP
```

## 6. Schedule News Collection With Cron

Edit crontab:

```bash
crontab -e
```

Run every 12 hours:

```cron
0 */12 * * * cd /opt/ai-daily-radar && git pull --ff-only && python3 scripts/update_ai_news.py && python3 scripts/validate_news_data.py && python3 scripts/generate_opinion.py >> /opt/ai-daily-radar/news-sync.log 2>&1
```

Check logs:

```bash
tail -n 100 /opt/ai-daily-radar/news-sync.log
```

## 7. Optional: systemd Timer Instead Of Cron

Create service:

```bash
sudo tee /etc/systemd/system/ai-news-sync.service >/dev/null <<'EOF'
[Unit]
Description=AI Daily Radar news sync

[Service]
Type=oneshot
WorkingDirectory=/opt/ai-daily-radar
ExecStart=/usr/bin/git pull --ff-only
ExecStart=/usr/bin/python3 scripts/update_ai_news.py
ExecStart=/usr/bin/python3 scripts/validate_news_data.py
ExecStart=/usr/bin/python3 scripts/generate_opinion.py
EnvironmentFile=/etc/ai-news-sync.env
EOF
```

If the app is deployed directly under an Nginx-owned directory such as `/var/www/ai-daily-radar`, make the service run as the same user that owns the writable files:

```ini
[Service]
Type=oneshot
User=www-data
Group=www-data
WorkingDirectory=/var/www/ai-daily-radar
ExecStart=/usr/bin/python3 scripts/update_ai_news.py
ExecStart=/usr/bin/python3 scripts/validate_news_data.py
ExecStart=/usr/bin/python3 scripts/generate_opinion.py
EnvironmentFile=/etc/ai-news-sync.env
```

This avoids `PermissionError` when the job updates `data/news.json`.

Set `AI_NEWS_MODEL` and a provider key in `/etc/ai-news-sync.env`, readable only by the service user. The default is OpenAI with `OPENAI_API_KEY`; for DeepSeek, set `AI_NEWS_PROVIDER=deepseek`, `AI_NEWS_MODEL=deepseek-flash`, and `DEEPSEEK_API_KEY`. For cron, provide those variables through a protected job environment before enabling the new command. The article generator runs without a human approval step. A failed generation keeps the previous article visible and writes failure status; check the job log and `data/opinion/status.json` for the last attempt.

Before enabling the systemd timer, create that environment file with permissions limited to the service user, for example `sudo install -m 600 -o www-data -g www-data /dev/null /etc/ai-news-sync.env`, then edit it locally. Do not put the model key in the repository or in browser code.

Create timer:

```bash
sudo tee /etc/systemd/system/ai-news-sync.timer >/dev/null <<'EOF'
[Unit]
Description=Run AI Daily Radar news sync every 12 hours

[Timer]
OnBootSec=5min
OnUnitActiveSec=12h
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-news-sync.timer
systemctl list-timers | grep ai-news-sync
```

Run manually:

```bash
sudo systemctl start ai-news-sync.service
sudo journalctl -u ai-news-sync.service -n 100 --no-pager
```

## 8. Frontend Acceptance Test On Linux

Install browser test dependencies:

```bash
cd /opt/ai-daily-radar
npm install
npx playwright install chromium
```

Run local server in one terminal:

```bash
python3 -m http.server 8000
```

Run frontend tests in another terminal:

```bash
SITE_URL=http://127.0.0.1:8000 npm run validate:frontend
```

Expected:

```text
7 passed
```

## 9. Deployment Checklist

- `http://SERVER_IP` opens the dashboard
- KPI numbers are visible
- News cards load from `data/news.json`
- Default date window is `今年`
- Date/source/category/keyword filters apply after clicking the query button
- Grade filter works
- Search works
- Reset works
- `python3 scripts/validate_news_data.py` passes
- Cron or systemd timer is active

## 10. Common Issues

If the page is blank:

```bash
curl -I http://127.0.0.1/data/news.json
python3 -m json.tool data/news.json >/dev/null
```

If Nginx returns 403:

```bash
sudo chmod -R a+rX /opt/ai-daily-radar
sudo nginx -t
sudo systemctl reload nginx
```

If cron does not run:

```bash
crontab -l
tail -n 100 /opt/ai-daily-radar/news-sync.log
```

If systemd timer does not update data:

```bash
systemctl status ai-news-sync.timer --no-pager
sudo systemctl start ai-news-sync.service
sudo journalctl -u ai-news-sync.service -n 100 --no-pager
ls -l data/news.json
```
