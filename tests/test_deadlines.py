import unittest
from datetime import datetime, timedelta, timezone

from app import apply_deadline_escalation


class DeadlineEscalationTest(unittest.TestCase):
    def test_deadline_within_48_hours_is_urgent(self):
        item = {
            "title": "Pressackreditering",
            "deadline_date": (datetime.now(timezone.utc) + timedelta(hours=30)).isoformat(),
            "score": 75,
        }

        escalated = apply_deadline_escalation([item])[0]

        self.assertTrue(escalated["deadline_urgent"])
        self.assertGreaterEqual(escalated["score"], 900)

    def test_deadline_far_away_is_not_urgent(self):
        item = {
            "title": "Pressackreditering senare",
            "deadline_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "score": 75,
        }

        escalated = apply_deadline_escalation([item])[0]

        self.assertNotIn("deadline_urgent", escalated)
        self.assertEqual(escalated["score"], 75)
