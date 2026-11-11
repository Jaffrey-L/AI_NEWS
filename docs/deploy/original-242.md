# Original site on 192.168.1.242

The original AI news URL is `http://192.168.1.242:8088/`. GitHub Pages
publishes the validated static edition. The original host mirrors that edition
every 15 minutes with `scripts/mirror_published_site.py`; it does not run AI
generation or need model credentials.

The mirror stages all four files under `/var/www/ai-news-mirror/releases/`,
validates the edition, then changes the `current` symlink atomically. An
incomplete download leaves the last working edition in service. Nginx serves
`/var/www/ai-news-mirror/current` on port 8088. The previous site's files and
`ai-news-sync.timer` remain in `/var/www/ai-daily-radar` for rollback.

Install the script as `/usr/local/libexec/ai-news-mirror.py`, create
`/var/www/ai-news-mirror/releases` owned by `www-data`, and install the
service, timer, and Nginx config from `deploy/242/`. Run the mirror once as
`www-data` before changing Nginx. Save the old Nginx config, run `nginx -t`,
then reload Nginx and enable the new timer.

Verify `/`, `/app.js`, `/workspace.css`, and `/data/site-payload.js` on port
8088 against the published Pages bytes. Confirm the weekly and Amazon tabs
open, original links work, and `ai-news-mirror.timer` is active.

To roll back, restore the saved `/etc/nginx/sites-enabled/ai-daily-radar`
config, run `nginx -t`, and reload Nginx. The old document root remains
intact. Stop the mirror timer if the old site should stay active.
