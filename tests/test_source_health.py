import unittest
import uuid

from desk import database


class SourceHealthTest(unittest.TestCase):
    def test_zero_runs_increment_and_reset_on_success(self):
        database.init_db()
        source_name = f"Testkälla {uuid.uuid4().hex}"

        database.update_source_health(source_name, 0)
        database.update_source_health(source_name, 0)

        rows = {row["source_name"]: row for row in database.source_health_rows()}
        self.assertEqual(rows[source_name]["consecutive_zero_runs"], 2)

        database.update_source_health(source_name, 3)

        rows = {row["source_name"]: row for row in database.source_health_rows()}
        self.assertEqual(rows[source_name]["consecutive_zero_runs"], 0)
        self.assertIsNotNone(rows[source_name]["last_success_at"])
