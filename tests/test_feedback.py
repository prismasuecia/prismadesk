import unittest
import uuid

from desk import database
from desk.models import NewsItem


class FeedbackTest(unittest.TestCase):
    def test_dismiss_item_hides_from_default_latest_items(self):
        database.init_db()
        marker = uuid.uuid4().hex
        item = NewsItem(
            source_name="Test",
            source_url="https://example.com",
            title=f"Test feedback {marker}",
            url=f"https://example.com/{marker}",
            hash=marker,
            priority="RED",
            desk="PRISMA",
            action_recommendation="PUBLICERA_IDAG",
            score=999,
        )
        database.save_items([item])

        with database.get_connection() as conn:
            row = conn.execute("SELECT id FROM items WHERE hash = ?", (marker,)).fetchone()
        item_id = int(row["id"])

        database.dismiss_item(item_id)
        database.record_feedback(item_id, "dismissed")

        default_ids = {int(row["id"]) for row in database.latest_items(limit=500)}
        all_ids = {int(row["id"]) for row in database.latest_items(limit=500, include_dismissed=True)}

        self.assertNotIn(item_id, default_ids)
        self.assertIn(item_id, all_ids)
