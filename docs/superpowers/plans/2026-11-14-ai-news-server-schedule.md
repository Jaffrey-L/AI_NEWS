# 242-triggered AI_NEWS refresh

## Goal

Move the **start time** of the Amazon daily and Monday weekly refresh to the 242 server. GitHub Actions continues to generate, validate, and publish the static site; the existing 242 mirror continues to copy the published result. A dedicated repository deploy key lets 242 push a marker to a trigger-only branch. No model key is copied to 242.

## Files and steps

1. Update `.github/workflows/refresh-editions.yml`: accept only marker pushes on `server-refresh` as refresh events, select Amazon versus weekly from the marker, check out `main` for data generation, and remove the delayed GitHub cron. Preserve regular `main` push deployment and manual dispatch.
2. Add `scripts/server_refresh_trigger.py`: run on 242 under a dedicated account, verify current public update status, create a marker on `server-refresh`, wait for the matching workflow and public/mirror freshness, and fail with a useful log if it cannot confirm success. Re-run attempts must not duplicate a successful issue.
3. Add `deploy/242/` service and timer units for Beijing 07:30 Amazon and Monday 08:30 weekly, with later retry slots; document setup, key ownership, operational checks, and rollback in `docs/deploy/linux-deploy.md`.
4. Add focused tests for date/status parsing, marker recognition, and retry/idempotence behavior. Run repository tests and workflow syntax checks.
5. Install a dedicated 242 deploy key with write access only to AI_NEWS, install script/units on 242, merge the repository change, trigger one controlled test run from 242, verify actual Actions completion plus public and 242 content, and record the next scheduled fire times.

## Boundaries

- `server-refresh` contains only generated trigger commits; server never pushes to `main`.
- The server does not receive the DeepSeek key or a broad personal GitHub token.
- Failed refresh retains the previous published content. A success report requires a matching successful workflow and current `updateStatus` on both public and 242 sites.
- If GitHub, article sources, or the model API fail, report the failure rather than claiming a guaranteed fresh article.
