import unittest
from datetime import datetime, timedelta, timezone

from desk import database


class RunsTest(unittest.TestCase):
    def test_stale_running_run_is_marked_failed(self):
        database.init_db()
        started_at = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(
            timespec="seconds"
        )
        with database.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (started_at, status) VALUES (?, ?)",
                (started_at, "RUNNING"),
            )
            run_id = int(cursor.lastrowid)

        changed = database.mark_stale_running_runs(max_age_minutes=10)

        with database.get_connection() as conn:
            row = conn.execute("SELECT status, finished_at, errors FROM runs WHERE id = ?", (run_id,)).fetchone()

        self.assertGreaterEqual(changed, 1)
        self.assertEqual(row["status"], "FAILED")
        self.assertIsNotNone(row["finished_at"])
        self.assertIn("avbröts", row["errors"])


if __name__ == "__main__":
    unittest.main()
