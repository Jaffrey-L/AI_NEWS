import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import server_refresh_trigger as trigger


class ServerRefreshChecks(unittest.TestCase):
    def test_beijing_day_and_marker(self):
        self.assertEqual(trigger.beijing_today(datetime(2026, 11, 14, 23, 45, tzinfo=timezone.utc)), date(2026, 11, 15))
        self.assertEqual(trigger.marker("weekly", date(2026, 11, 16)), "server-refresh: weekly 2026-11-16")
        with self.assertRaises(ValueError):
            trigger.marker("both", date(2026, 11, 16))

    def test_only_successful_current_beijing_status_counts(self):
        target = date(2026, 11, 15)
        payload = {"updateStatus": {"amazon": {"state": "ok", "checkedAt": "2026-11-14T16:02:00+00:00"}}}
        self.assertTrue(trigger.checked_today(payload, "amazon", target))
        self.assertFalse(trigger.checked_today(payload, "amazon", date(2026, 11, 14)))
        payload["updateStatus"]["amazon"]["state"] = "failed"
        self.assertFalse(trigger.checked_today(payload, "amazon", target))
        payload["updateStatus"]["amazon"] = {"state": "ok", "checkedAt": "bad time"}
        self.assertFalse(trigger.checked_today(payload, "amazon", target))

    def test_dispatch_run_matches_exact_server_commit(self):
        sha = "a" * 40
        rows = [
            {"event": "workflow_dispatch", "display_title": "Refresh amazon " + "b" * 40, "head_branch": "main"},
            {"event": "workflow_dispatch", "display_title": f"Refresh amazon {sha}", "head_branch": "main"},
        ]
        with patch.object(trigger, "runs", return_value=rows):
            self.assertIs(trigger.matching_run("workflow_dispatch", sha, "amazon"), rows[1])
            self.assertIsNone(trigger.matching_run("workflow_dispatch", sha, "weekly"))

    def test_public_and_mirror_must_both_be_fresh(self):
        day = date(2026, 11, 15)
        with patch.object(trigger, "fresh", side_effect=[True, False, True, True]) as fresh, patch.object(trigger.time, "sleep"):
            trigger.wait_public_and_mirror("amazon", day, minutes=1)
        self.assertEqual(fresh.call_count, 4)


if __name__ == "__main__":
    unittest.main()
