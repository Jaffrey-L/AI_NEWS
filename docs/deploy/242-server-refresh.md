# AI_NEWS refresh initiated by 242

The 242 server schedules the refresh. GitHub Actions still generates, validates,
commits and publishes the site; the existing `ai-news-mirror.timer` copies the
published static site to port 8088. The separate `ai-news-sync.timer` belongs to
AI Daily Radar and must not be changed.

## Schedule and proof

- `ai-news-refresh-amazon.timer`: every day at 07:30 Beijing time, with 09:00
  and 11:00 recovery slots. It skips generation if today's Amazon status is
  already `ok` and waits for the 242 mirror when needed.
- `ai-news-refresh-weekly.timer`: Monday 08:30, with 10:00 and 12:00 recovery
  slots. It publishes the completed weekly issue.
- A dedicated deploy key can push only to the AI_NEWS repository. The server
  script writes a marker to `server-refresh`; a small workflow then dispatches
  `refresh-editions.yml` on `main`. The model API key remains solely in GitHub
  Actions secrets. The server never pushes to `main`.
- The server service reports success only after the matching push and dispatch
  workflow runs succeed **and** both the public site and 242 mirror show an
  `ok` update with a Beijing date matching the trigger day. Failures stay in
  `journalctl -u 'ai-news-refresh@*'` and leave the previous site intact.

## Installation on 242

Install a dedicated non-login `ai-news-trigger` system account and an Ed25519
deploy key under `/var/lib/ai-news-trigger/.ssh` (key mode 0600, directory
0700). Add only the public key to this repository's deploy keys with write
access. Verify the `github.com` host key against GitHub's published Ed25519
fingerprint before placing it in that account's `known_hosts`.

Install `scripts/server_refresh_trigger.py` as
`/usr/local/libexec/ai-news-refresh-trigger.py` (root owned, 0644). Install
`deploy/242/ai-news-refresh@.service` and the two timer files under
`/etc/systemd/system/` (root owned, 0644). The server timezone must be
`Asia/Shanghai`. Validate units with `systemd-analyze verify`, reload systemd,
enable/start both timers, and inspect `systemctl list-timers` for the next
07:30/08:30 triggers.

The deploy key has repository write authority; revoke the GitHub deploy key
and remove its server private key together if the server is retired or the key
is suspected compromised. Do not copy a personal GitHub token or DeepSeek key
to 242.

## Checks and recovery

For a current day, inspect:

```text
systemctl status ai-news-refresh-amazon.timer ai-news-refresh-weekly.timer
journalctl -u ai-news-refresh@amazon.service -u ai-news-refresh@weekly.service --since today --no-pager
```

The exact GitHub workflow run URLs appear in the service log. If a run failed,
fix the source/model problem and start the relevant service once; the trigger
script retries only when the public issue is not already fresh. Use
`workflow_dispatch` as an emergency manual fallback. The 242 mirror may lag
the public site by one 15-minute mirror interval.

To roll back the new scheduler, disable the two new timers and revert the
workflow change to restore the previous GitHub `schedule` entries. Do not
disable `ai-news-mirror.timer`.
