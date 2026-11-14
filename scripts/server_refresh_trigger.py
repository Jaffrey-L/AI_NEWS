"""Start AI_NEWS refreshes from 242 and verify the published result.

GitHub still performs generation and Pages publishing. This process has only a
repository deploy key, so it can push a marker but cannot read model secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPOSITORY = "Jaffrey-L/AI_NEWS"
BRANCH = "server-refresh"
WORKFLOW = "refresh-editions.yml"
PUBLIC_PAYLOAD = "https://jaffrey-l.github.io/AI_NEWS/data/site-payload.js"
MIRROR_PAYLOAD = "http://192.168.1.242:8088/data/site-payload.js"
HOME = Path("/var/lib/ai-news-trigger")
BEIJING = timezone(timedelta(hours=8))


def beijing_today(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(BEIJING).date()


def marker(mode: str, day: date) -> str:
    if mode not in {"amazon", "weekly"}:
        raise ValueError("invalid refresh mode")
    return f"server-refresh: {mode} {day.isoformat()}"


def checked_today(payload: dict, mode: str, day: date) -> bool:
    row = payload.get("updateStatus", {}).get(mode, {})
    if row.get("state") != "ok":
        return False
    checked_at = row.get("checkedAt")
    if not isinstance(checked_at, str):
        return False
    try:
        timestamp = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return timestamp.tzinfo is not None and timestamp.astimezone(BEIJING).date() == day


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "ai-news-242-refresh/1", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def get_payload(url: str) -> dict:
    request = urllib.request.Request(f"{url}?probe={int(time.time())}", headers={"User-Agent": "ai-news-242-refresh/1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000:
        raise RuntimeError("published payload exceeds expected size")
    prefix = b"window.AI_NEWS_DATA = "
    if not raw.startswith(prefix):
        raise RuntimeError("published payload has unexpected format")
    return json.loads(raw[len(prefix):].rstrip(b";\r\n "))


def fresh(url: str, mode: str, day: date) -> bool:
    try:
        return checked_today(get_payload(url), mode, day)
    except Exception as exc:
        print(f"status check unavailable for {url}: {type(exc).__name__}: {exc}", flush=True)
        return False


def runs(event: str) -> list[dict]:
    query = urllib.parse.urlencode({"event": event, "per_page": 30})
    url = f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/{WORKFLOW}/runs?{query}"
    return get_json(url).get("workflow_runs", [])


def matching_run(event: str, sha: str, mode: str) -> dict | None:
    for run in runs(event):
        if event == "push" and run.get("head_branch") == BRANCH and run.get("head_sha") == sha:
            return run
        if event == "workflow_dispatch" and run.get("display_title") == f"Refresh {mode} {sha}" and run.get("head_branch") == "main":
            return run
    return None


def wait_run(event: str, sha: str, mode: str, minutes: int = 45) -> dict:
    deadline = time.monotonic() + minutes * 60
    while time.monotonic() < deadline:
        try:
            run = matching_run(event, sha, mode)
        except Exception as exc:
            print(f"GitHub run check failed: {type(exc).__name__}: {exc}", flush=True)
            run = None
        if run and run.get("status") == "completed":
            if run.get("conclusion") != "success":
                raise RuntimeError(f"{event} workflow failed: {run.get('html_url')} ({run.get('conclusion')})")
            print(f"{event} workflow passed: {run.get('html_url')}", flush=True)
            return run
        time.sleep(90)
    raise TimeoutError(f"No successful {event} workflow observed for {sha} within {minutes} minutes")


def git(cwd: Path, *args: str, env: dict) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, env=env, text=True, capture_output=True, timeout=120, check=False)
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr[-500:]}")
    return result.stdout.strip()


def ssh_environment() -> dict:
    key = HOME / ".ssh" / "id_ed25519"
    known_hosts = HOME / ".ssh" / "known_hosts"
    if not key.is_file() or not known_hosts.is_file():
        raise RuntimeError("dedicated deploy key or verified known_hosts missing")
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f"ssh -i {key} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile={known_hosts} -o BatchMode=yes"
    return env


def push_marker(mode: str, day: date) -> str:
    env = ssh_environment()
    with tempfile.TemporaryDirectory(prefix="ai-news-trigger-") as directory:
        root = Path(directory)
        git(root, "clone", "--quiet", f"git@github.com:{REPOSITORY}.git", "repo", env=env)
        repo = root / "repo"
        git(repo, "config", "user.name", "AI_NEWS 242 scheduler", env=env)
        git(repo, "config", "user.email", "ai-news-242@users.noreply.github.com", env=env)
        if git(repo, "branch", "--remotes", "--list", f"origin/{BRANCH}", env=env):
            git(repo, "checkout", "--quiet", "--track", f"origin/{BRANCH}", env=env)
            git(repo, "merge", "--quiet", "--no-edit", "origin/main", env=env)
        else:
            git(repo, "checkout", "--quiet", "-b", BRANCH, "origin/main", env=env)
        git(repo, "commit", "--quiet", "--allow-empty", "-m", marker(mode, day), env=env)
        sha = git(repo, "rev-parse", "HEAD", env=env)
        git(repo, "push", "--quiet", "origin", f"HEAD:refs/heads/{BRANCH}", env=env)
        print(f"242 pushed {marker(mode, day)} at {sha}", flush=True)
        return sha


def previous_marker(mode: str, day: date) -> str | None:
    env = ssh_environment()
    with tempfile.TemporaryDirectory(prefix="ai-news-check-") as directory:
        root = Path(directory)
        git(root, "clone", "--quiet", f"git@github.com:{REPOSITORY}.git", "repo", env=env)
        repo = root / "repo"
        if not git(repo, "branch", "--remotes", "--list", f"origin/{BRANCH}", env=env):
            return None
        log = git(repo, "log", "-30", "--format=%H%x09%s", f"origin/{BRANCH}", env=env)
        for line in log.splitlines():
            sha, _, subject = line.partition("\t")
            if subject == marker(mode, day):
                return sha
    return None


def wait_public_and_mirror(mode: str, day: date, minutes: int = 20) -> None:
    deadline = time.monotonic() + minutes * 60
    while time.monotonic() < deadline:
        public_ok = fresh(PUBLIC_PAYLOAD, mode, day)
        mirror_ok = fresh(MIRROR_PAYLOAD, mode, day)
        if public_ok and mirror_ok:
            print(f"published and 242 mirror both fresh for {mode} {day}", flush=True)
            return
        time.sleep(60)
    raise TimeoutError("Workflow passed but public site and 242 mirror did not both become fresh")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("amazon", "weekly"), required=True)
    parser.add_argument("--force", action="store_true", help="Trigger a controlled same-day test even when already fresh")
    args = parser.parse_args()
    day = beijing_today()
    if args.mode == "weekly" and day.weekday() != 0 and not args.force:
        raise RuntimeError("weekly refresh is scheduled for Monday only")
    HOME.mkdir(parents=True, exist_ok=True)
    import fcntl  # Linux service only; pure helpers remain importable on Windows.
    with (HOME / "trigger.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if fresh(PUBLIC_PAYLOAD, args.mode, day) and not args.force:
            print(f"public issue already fresh for {args.mode} {day}", flush=True)
            wait_public_and_mirror(args.mode, day)
            return 0
        prior_sha = previous_marker(args.mode, day)
        if prior_sha and not args.force:
            prior = matching_run("workflow_dispatch", prior_sha, args.mode)
            if prior and prior.get("status") != "completed":
                print(f"resuming in-progress refresh {prior_sha}", flush=True)
                wait_run("workflow_dispatch", prior_sha, args.mode)
                wait_public_and_mirror(args.mode, day)
                return 0
            if prior and prior.get("conclusion") == "success":
                print(f"checking previously successful refresh {prior_sha}", flush=True)
                try:
                    wait_public_and_mirror(args.mode, day, minutes=5)
                    return 0
                except TimeoutError:
                    print("previous success did not publish current data; retrying", flush=True)
        sha = push_marker(args.mode, day)
        wait_run("push", sha, args.mode, minutes=15)
        wait_run("workflow_dispatch", sha, args.mode)
        wait_public_and_mirror(args.mode, day)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
